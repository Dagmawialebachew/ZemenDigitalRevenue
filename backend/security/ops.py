from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from backend.core.config import get_settings


def require_ops_api(authorization: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    expected = settings.ops_api_key
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OPS_API_KEY not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid operations credential")
