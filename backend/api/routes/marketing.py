from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.core.config import Settings, get_settings
from backend.security.control import ControlPrincipal, require_control_session
from backend.services.marketing import MarketingService

router = APIRouter(prefix="/api/control/marketing", tags=["marketing"])


def _service(request: Request, settings: Settings) -> MarketingService:
    return MarketingService(request.app.state.db, settings, getattr(request.app.state, "bot", None))


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=500, detail="Marketing operation failed")


class AudienceCountRequest(BaseModel):
    audience_definition: dict[str, Any] = Field(default_factory=dict)


class BroadcastSave(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    audience_definition: dict[str, Any] = Field(default_factory=dict)
    content_am: dict[str, Any] | None = None
    content_en: dict[str, Any] | None = None
    attribution_window_hours: int = Field(default=168, ge=1, le=2160)
    expected_revision: int | None = None


class BroadcastSchedule(BaseModel):
    scheduled_at: datetime | None = None


class AutomationSave(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    product_id: UUID | None = None
    trigger_event: str = Field(min_length=1, max_length=100)
    is_enabled: bool = False
    stop_conditions: list[dict[str, Any]] = Field(default_factory=list)
    audience_definition: dict[str, Any] = Field(default_factory=dict)
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=1, le=1000)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=30)
    expected_revision: int | None = None


class EnabledAction(BaseModel):
    enabled: bool


class DiscountRuleCreate(BaseModel):
    product_id: UUID
    name: str = Field(default="Recovery offer", min_length=1, max_length=180)
    rule_type: str = "recovery"
    target_price_br: str | float | int
    eligibility_delay_seconds: int = Field(default=0, ge=0)
    expires_after_seconds: int | None = Field(default=None, ge=60)
    is_active: bool = True
    require_no_pending_payment: bool = True
    minimum_intent_score: int = Field(default=0, ge=0, le=1000)
    expected_revision: int | None = None


class TrackingLinkCreate(BaseModel):
    product_id: UUID | None = None
    label: str | None = Field(default=None, max_length=180)
    source: str = Field(default="Meta", max_length=100)
    platform: str | None = Field(default=None, max_length=100)
    campaign: str | None = Field(default=None, max_length=180)
    ad_set: str | None = Field(default=None, max_length=180)
    creative: str | None = Field(default=None, max_length=180)
    angle: str | None = Field(default=None, max_length=180)
    language_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PayoutCreate(BaseModel):
    referrer_user_id: UUID
    payout_method: str
    payout_destination: str = Field(min_length=1, max_length=300)
    note: str | None = Field(default=None, max_length=1000)


class PayoutPaid(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.get("")
async def marketing_dashboard(
    request: Request,
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await _service(request, settings).dashboard()


@router.post("/audience/count")
async def audience_count(
    payload: AudienceCountRequest,
    request: Request,
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, int]:
    try:
        return {"count": await _service(request, settings).audience_count(payload.audience_definition)}
    except Exception as exc:
        raise _error(exc) from None


@router.post("/broadcasts", status_code=status.HTTP_201_CREATED)
async def create_broadcast(payload: BroadcastSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try:
        return await _service(request, settings).create_broadcast(admin_telegram_id=principal.telegram_id, data=payload.model_dump(exclude={"expected_revision"}))
    except Exception as exc: raise _error(exc) from None


@router.patch("/broadcasts/{broadcast_id}")
async def update_broadcast(broadcast_id: UUID, payload: BroadcastSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    if payload.expected_revision is None:
        raise HTTPException(status_code=400, detail="expected_revision is required")
    try:
        return await _service(request, settings).update_broadcast(broadcast_id=broadcast_id, admin_telegram_id=principal.telegram_id, expected_revision=payload.expected_revision, data=payload.model_dump(exclude={"expected_revision"}))
    except Exception as exc: raise _error(exc) from None


@router.post("/broadcasts/{broadcast_id}/schedule")
async def schedule_broadcast(broadcast_id: UUID, payload: BroadcastSchedule, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try:
        return await _service(request, settings).schedule_broadcast(broadcast_id=broadcast_id, admin_telegram_id=principal.telegram_id, scheduled_at=payload.scheduled_at)
    except Exception as exc: raise _error(exc) from None


@router.post("/broadcasts/{broadcast_id}/cancel")
async def cancel_broadcast(broadcast_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try:
        return await _service(request, settings).cancel_broadcast(broadcast_id=broadcast_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc: raise _error(exc) from None


@router.post("/broadcast-media/upload")
async def upload_broadcast_media(
    request: Request,
    file: UploadFile = File(...),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
):
    data = await file.read((settings.marketing_upload_max_mb * 1024 * 1024) + 1)
    try:
        return await _service(request, settings).upload_broadcast_media(filename=file.filename or "broadcast.bin", content_type=file.content_type, data=data)
    except Exception as exc: raise _error(exc) from None


@router.get("/automations/{automation_id}")
async def automation_detail(automation_id: UUID, request: Request, _: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).automation_detail(automation_id)
    except Exception as exc: raise _error(exc) from None


@router.post("/automations", status_code=status.HTTP_201_CREATED)
async def create_automation(payload: AutomationSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).create_automation(admin_telegram_id=principal.telegram_id, data=payload.model_dump(exclude={"expected_revision"}, mode="json"))
    except Exception as exc: raise _error(exc) from None


@router.patch("/automations/{automation_id}")
async def update_automation(automation_id: UUID, payload: AutomationSave, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    if payload.expected_revision is None: raise HTTPException(status_code=400, detail="expected_revision is required")
    try: return await _service(request, settings).update_automation(automation_id=automation_id, admin_telegram_id=principal.telegram_id, expected_revision=payload.expected_revision, data=payload.model_dump(exclude={"expected_revision"}, mode="json"))
    except Exception as exc: raise _error(exc) from None


@router.post("/automations/{automation_id}/enabled")
async def set_automation_enabled(automation_id: UUID, payload: EnabledAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).set_automation_enabled(automation_id=automation_id, admin_telegram_id=principal.telegram_id, enabled=payload.enabled)
    except Exception as exc: raise _error(exc) from None


@router.post("/discount-rules", status_code=status.HTTP_201_CREATED)
async def create_discount_rule(payload: DiscountRuleCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).create_discount_rule(admin_telegram_id=principal.telegram_id, data=payload.model_dump(exclude={"expected_revision"}, mode="json"))
    except Exception as exc: raise _error(exc) from None


@router.patch("/discount-rules/{rule_id}")
async def update_discount_rule(rule_id: UUID, payload: DiscountRuleCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    if payload.expected_revision is None:
        raise HTTPException(status_code=400, detail="expected_revision is required")
    try:
        return await _service(request, settings).update_discount_rule(
            rule_id=rule_id, admin_telegram_id=principal.telegram_id,
            expected_revision=payload.expected_revision,
            data=payload.model_dump(exclude={"expected_revision"}, mode="json"),
        )
    except Exception as exc:
        raise _error(exc) from None


@router.post("/discount-rules/{rule_id}/enabled")
async def set_discount_rule_enabled(rule_id: UUID, payload: EnabledAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).set_discount_rule_active(rule_id=rule_id, admin_telegram_id=principal.telegram_id, active=payload.enabled)
    except Exception as exc: raise _error(exc) from None


@router.post("/links", status_code=status.HTTP_201_CREATED)
async def create_link(payload: TrackingLinkCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).create_tracking_link(admin_telegram_id=principal.telegram_id, data=payload.model_dump(mode="json"))
    except Exception as exc: raise _error(exc) from None


@router.post("/links/{link_id}/enabled")
async def set_link_enabled(link_id: UUID, payload: EnabledAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).set_tracking_link_active(link_id=link_id, admin_telegram_id=principal.telegram_id, active=payload.enabled)
    except Exception as exc: raise _error(exc) from None


@router.post("/payouts", status_code=status.HTTP_201_CREATED)
async def create_payout(payload: PayoutCreate, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).create_payout(referrer_user_id=payload.referrer_user_id, admin_telegram_id=principal.telegram_id, payout_method=payload.payout_method, payout_destination=payload.payout_destination, note=payload.note)
    except Exception as exc: raise _error(exc) from None


@router.post("/payouts/{payout_id}/paid")
async def payout_paid(payout_id: UUID, payload: PayoutPaid, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)):
    try: return await _service(request, settings).mark_payout_paid(payout_id=payout_id, admin_telegram_id=principal.telegram_id, note=payload.note)
    except Exception as exc: raise _error(exc) from None
