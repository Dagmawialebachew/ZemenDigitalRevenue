from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from backend.api.schemas.miniapp import (
    MiniAppLanguageRequest,
    MiniAppProductActionRequest,
    MiniAppReviewRequest,
    MiniAppSessionRequest,
)
from backend.core.config import Settings, get_settings
from backend.services.miniapp import MiniAppService
from backend.security.miniapp import MiniAppAuthError

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing session")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    return token.strip()


async def current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> Any:
    token = _bearer_token(authorization)
    service = MiniAppService(request.app.state.db, settings)
    try:
        return await service.user_from_session_token(token)
    except (MiniAppAuthError, LookupError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="expired or invalid Mini App session",
        ) from None


@router.post("/session")
async def create_session(
    body: MiniAppSessionRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured",
        )
    service = MiniAppService(request.app.state.db, settings)
    try:
        auth = await service.authenticate_init_data(init_data=body.init_data)
    except MiniAppAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from None
    return {
        "session_token": auth.session_token,
        "expires_in": auth.session_expires_in,
        "focus_product_slug": auth.focus_product_slug,
        "user": {
            "telegram_id": auth.telegram_id,
            "first_name": auth.first_name,
            "username": auth.username,
            "language": auth.preferred_language,
            "is_new_user": auth.is_new_user,
        },
    }


@router.get("/bootstrap")
async def bootstrap(
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
    language: str = Query(default="am", pattern=r"^(am|en)$"),
) -> dict[str, object]:
    return await MiniAppService(request.app.state.db, settings).bootstrap(
        user_id=user["id"], language=language
    )


@router.get("/products")
async def products(
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
    language: str = Query(default="am", pattern=r"^(am|en)$"),
) -> dict[str, object]:
    data = await MiniAppService(request.app.state.db, settings).bootstrap(
        user_id=user["id"], language=language
    )
    return {"products": data["products"]}


@router.get("/policies/{kind}")
async def policy(
    kind: str,
    request: Request,
    _: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
    language: str = Query(default="am", pattern=r"^(am|en)$"),
) -> dict[str, object]:
    try:
        return MiniAppService(request.app.state.db, settings).policy(
            kind=kind, language=language
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found") from None


@router.get("/products/{slug}")
async def product_detail(
    slug: str,
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
    language: str = Query(default="am", pattern=r"^(am|en)$"),
) -> dict[str, object]:
    try:
        return await MiniAppService(request.app.state.db, settings).product_detail(
            user_id=user["id"], slug=slug, language=language
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found") from None


@router.post("/products/{slug}/checkout")
async def create_checkout(
    slug: str,
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await MiniAppService(request.app.state.db, settings).create_checkout(
            user_id=user["id"], slug=slug
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post("/products/{slug}/action")
async def product_action(
    slug: str,
    body: MiniAppProductActionRequest,
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await MiniAppService(request.app.state.db, settings).record_product_action(
            user_id=user["id"], slug=slug, action=body.action
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found") from None


@router.get("/library")
async def library(
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
    language: str = Query(default="am", pattern=r"^(am|en)$"),
) -> dict[str, object]:
    items = await MiniAppService(request.app.state.db, settings).library(
        user_id=user["id"], language=language
    )
    return {"items": items}


@router.post("/products/{slug}/review")
async def submit_review(
    slug: str,
    body: MiniAppReviewRequest,
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return await MiniAppService(request.app.state.db, settings).submit_review(
            user_id=user["id"],
            slug=slug,
            rating=body.rating,
            review_text=body.review_text,
            language=body.language,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from None
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.get("/referrals")
async def referrals(
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return await MiniAppService(request.app.state.db, settings).referral_center(
        user_id=user["id"]
    )


@router.patch("/me/language")
async def change_language(
    body: MiniAppLanguageRequest,
    request: Request,
    user: Any = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    return await MiniAppService(request.app.state.db, settings).change_language(
        user_id=user["id"], language=body.language
    )
