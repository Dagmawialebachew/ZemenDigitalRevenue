from __future__ import annotations

import io
import mimetypes
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.config import Settings, get_settings
from backend.repositories.control import ControlRepository
from backend.security.control import (
    ControlPrincipal,
    ControlSessionCodec,
    csrf_token_for_session,
    login_fingerprint,
    require_control_session,
    verify_owner_key,
)
from backend.services.control import ControlService
from backend.services.payments import PaymentService

router = APIRouter(prefix="/api/control", tags=["zemen-control"])


class LoginRequest(BaseModel):
    access_key: str = Field(min_length=1, max_length=512)
    telegram_id: int


class PaymentAction(BaseModel):
    proof_id: UUID | None = None


class PaymentRejectAction(PaymentAction):
    reason: str
    reason_text: str | None = Field(default=None, max_length=1000)


class SupportReplyAction(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _service(request: Request, settings: Settings) -> ControlService:
    return ControlService(request.app.state.db, settings)


async def _admin_profile(request: Request, telegram_id: int) -> dict[str, object]:
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id,telegram_id,display_name,role FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            telegram_id,
        )
    if row:
        return dict(row)
    return {"id": None, "telegram_id": telegram_id, "display_name": "Zemen Admin", "role": "owner"}


@router.post("/auth/login")
async def login(payload: LoginRequest, response: Response, request: Request, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    if not settings.control_owner_key or not settings.control_session_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Control Room authentication is not configured")

    remote_host = request.client.host if request.client else "unknown"
    fingerprint = login_fingerprint(
        remote_host=remote_host, telegram_id=payload.telegram_id, secret=settings.control_session_secret
    )
    async with request.app.state.db.acquire() as conn:
        # Keep durable rate-limit evidence bounded without adding another queue.
        await conn.execute("DELETE FROM control_login_attempts WHERE attempted_at < now()-interval '30 days'")
        failed_count = await conn.fetchval(
            """SELECT count(*) FROM control_login_attempts
               WHERE fingerprint_hash=$1 AND succeeded=FALSE
                 AND attempted_at >= now()-make_interval(secs=>$2::int)""",
            fingerprint, settings.control_login_window_seconds,
        )
    if int(failed_count or 0) >= settings.control_login_max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed sign-in attempts. Try again later.")

    valid_key = verify_owner_key(payload.access_key, settings.control_owner_key)
    allowed = False
    if valid_key:
        allowed, _ = await PaymentService(request.app.state.db, settings).is_admin(telegram_id=payload.telegram_id)
    succeeded = bool(valid_key and allowed)
    async with request.app.state.db.acquire() as conn:
        await conn.execute(
            "INSERT INTO control_login_attempts(telegram_id,fingerprint_hash,succeeded) VALUES($1,$2,$3)",
            payload.telegram_id, fingerprint, succeeded,
        )
    if not valid_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access key")
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Telegram admin ID is not authorized")

    token = ControlSessionCodec(settings.control_session_secret).encode(
        telegram_id=payload.telegram_id,
        ttl_seconds=settings.control_session_ttl_seconds,
    )
    response.set_cookie(
        settings.control_cookie_name,
        token,
        max_age=settings.control_session_ttl_seconds,
        httponly=True,
        secure=settings.control_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {
        "authenticated": True,
        "admin": await _admin_profile(request, payload.telegram_id),
        "csrf_token": csrf_token_for_session(token, settings.control_session_secret),
    }


@router.post("/auth/logout")
async def logout(response: Response, settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    response.delete_cookie(settings.control_cookie_name, path="/")
    return {"authenticated": False}


@router.get("/auth/me")
async def me(
    request: Request,
    principal: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    token = request.cookies.get(settings.control_cookie_name, "")
    return {
        "authenticated": True,
        "admin": await _admin_profile(request, principal.telegram_id),
        "csrf_token": csrf_token_for_session(token, settings.control_session_secret),
    }


@router.get("/overview")
async def overview(
    request: Request,
    days: Literal[7, 14, 30, 90] = Query(default=14),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return await _service(request, settings).overview(days=days)


@router.get("/payments")
async def payments(
    request: Request,
    payment_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).payments(status=payment_status, limit=limit, offset=offset)}


@router.get("/orders")
async def orders(
    request: Request,
    order_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).orders(status=order_status, limit=limit, offset=offset)}


@router.get("/deliveries")
async def deliveries(
    request: Request,
    delivery_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).deliveries(status=delivery_status, limit=limit, offset=offset)}


@router.get("/customers")
async def customers(
    request: Request,
    search: str | None = Query(default=None, max_length=120),
    stage: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).customers(search=search, stage=stage, limit=limit, offset=offset)}


@router.get("/customers/{user_id}")
async def customer_detail(
    user_id: UUID,
    request: Request,
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    data = await _service(request, settings).customer_detail(user_id=user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return data


@router.get("/support")
async def support_cases(
    request: Request,
    support_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).support(status=support_status, limit=limit, offset=offset)}


@router.get("/support/{case_public_id}")
async def support_thread(case_public_id: str, request: Request, _: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    data = await _service(request, settings).support_thread(case_public_id=case_public_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Support case not found")
    return data


@router.get("/alerts")
async def alerts(
    request: Request,
    alert_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _: ControlPrincipal = Depends(require_control_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"items": await _service(request, settings).alerts(status=alert_status, limit=limit, offset=offset)}


@router.get("/payment-proofs/{proof_id}/image")
async def payment_proof_image(
    proof_id: UUID,
    request: Request,
    _: ControlPrincipal = Depends(require_control_session),
) -> StreamingResponse:
    async with request.app.state.db.acquire() as conn:
        proof = await ControlRepository().proof(conn, proof_id=proof_id)
    if proof is None:
        raise HTTPException(status_code=404, detail="Payment proof not found")
    bot = request.app.state.bot
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not connected")
    try:
        tg_file = await bot.get_file(proof["telegram_file_id"])
        stream = io.BytesIO()
        await bot.download(proof["telegram_file_id"], destination=stream)
        stream.seek(0)
        mime = mimetypes.guess_type(tg_file.file_path or "proof.jpg")[0] or "image/jpeg"
        return StreamingResponse(stream, media_type=mime, headers={"Cache-Control": "private, max-age=120"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load Telegram proof: {type(exc).__name__}") from None


def _translate_action_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Operation failed")


@router.post("/payments/{payment_public_id}/approve")
async def approve_payment(payment_public_id: str, payload: PaymentAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).approve_payment(payment_public_id=payment_public_id, proof_id=payload.proof_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/payments/{payment_public_id}/flag")
async def flag_payment(payment_public_id: str, payload: PaymentAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).flag_payment(payment_public_id=payment_public_id, proof_id=payload.proof_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/payments/{payment_public_id}/reject")
async def reject_payment(payment_public_id: str, payload: PaymentRejectAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).reject_payment(payment_public_id=payment_public_id, proof_id=payload.proof_id, admin_telegram_id=principal.telegram_id, reason=payload.reason, reason_text=payload.reason_text)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/deliveries/{entitlement_id}/retry")
async def retry_delivery(entitlement_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).retry_delivery(entitlement_id=entitlement_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/support/{case_public_id}/reply")
async def support_reply(case_public_id: str, payload: SupportReplyAction, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).reply_support(case_public_id=case_public_id, admin_telegram_id=principal.telegram_id, text=payload.text)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/support/{case_public_id}/resolve")
async def resolve_support(case_public_id: str, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await _service(request, settings).resolve_support(case_public_id=case_public_id, admin_telegram_id=principal.telegram_id)
    except Exception as exc:
        raise _translate_action_error(exc) from None


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: UUID, request: Request, principal: ControlPrincipal = Depends(require_control_session), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return await _service(request, settings).resolve_alert(alert_id=alert_id, admin_telegram_id=principal.telegram_id)
