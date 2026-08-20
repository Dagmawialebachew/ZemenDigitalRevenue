from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.core.config import Settings, get_settings
from backend.security.control import ControlPrincipal, require_control_session
from backend.services.final_control import FinalControlService

router = APIRouter(prefix="/api/control/final", tags=["zemen-control-final"])


class ExpenseCreate(BaseModel):
    expense_date: date
    category: str
    amount_br: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=250)


class ReviewModeration(BaseModel):
    status: str = Field(pattern="^(approved|rejected|pending)$")
    featured: bool = False


class SettingUpdate(BaseModel):
    value: object


class AdminUpsert(BaseModel):
    telegram_id: int
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(pattern="^(owner|admin|operator|viewer)$")


class AdminActive(BaseModel):
    active: bool


def _service(request: Request, settings: Settings) -> FinalControlService:
    return FinalControlService(request.app.state.db, settings)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Operation failed")


@router.get("/analytics")
async def analytics(
    request: Request,
    days: int = Query(default=30, ge=7, le=365),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return await _service(request, settings).analytics(days=days)


@router.get("/financials")
async def financials(
    request: Request,
    days: int = Query(default=30, ge=7, le=365),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return await _service(request, settings).financials(days=days)


@router.post("/financials/expenses", status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).create_expense(
            admin_telegram_id=principal.telegram_id,
            expense_date=payload.expense_date,
            category=payload.category,
            amount_br=payload.amount_br,
            description=payload.description,
            reference=payload.reference,
        )
    except Exception as exc:
        raise _http_error(exc) from None


@router.delete("/financials/expenses/{expense_id}")
async def delete_expense(
    expense_id: UUID,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).delete_expense(
            admin_telegram_id=principal.telegram_id,
            expense_id=expense_id,
        )
    except Exception as exc:
        raise _http_error(exc) from None


@router.get("/reviews")
async def reviews(
    request: Request,
    review_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).reviews(status=review_status, limit=limit, offset=offset)}


@router.post("/reviews/{review_id}/moderate")
async def moderate_review(
    review_id: UUID,
    payload: ReviewModeration,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).moderate_review(
            admin_telegram_id=principal.telegram_id,
            review_id=review_id,
            status=payload.status,
            featured=payload.featured,
        )
    except Exception as exc:
        raise _http_error(exc) from None


@router.get("/settings")
async def settings_bundle(
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).settings_bundle(admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _http_error(exc) from None


@router.put("/settings/{key:path}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).set_setting(
            admin_telegram_id=principal.telegram_id,
            key=key,
            value=payload.value,
        )
    except Exception as exc:
        raise _http_error(exc) from None


@router.post("/admins")
async def upsert_admin(
    payload: AdminUpsert,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).upsert_admin(
            actor_telegram_id=principal.telegram_id,
            telegram_id=payload.telegram_id,
            display_name=payload.display_name,
            role=payload.role,
        )
    except Exception as exc:
        raise _http_error(exc) from None


@router.post("/admins/{admin_id}/active")
async def set_admin_active(
    admin_id: UUID,
    payload: AdminActive,
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await _service(request, settings).set_admin_active(
            actor_telegram_id=principal.telegram_id,
            admin_id=admin_id,
            active=payload.active,
        )
    except Exception as exc:
        raise _http_error(exc) from None
