from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.core.config import Settings
from backend.security.control import ControlSessionCodec, csrf_token_for_session


_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
_LOGIN_PATH = "/api/control/auth/login"


class ControlMutationGuardMiddleware(BaseHTTPMiddleware):
    """CSRF + read-only-role enforcement for all Control Room mutations.

    Keeping this at the HTTP boundary means an old or future dashboard route cannot
    accidentally forget to add a per-route CSRF dependency.
    """

    def __init__(self, app, *, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        path = request.url.path
        if not path.startswith("/api/control") or request.method.upper() not in _UNSAFE or path == _LOGIN_PATH:
            return await call_next(request)

        token = request.cookies.get(self.settings.control_cookie_name, "")
        supplied = request.headers.get("X-CSRF-Token", "")
        expected = csrf_token_for_session(token, self.settings.control_session_secret)
        if not token or not supplied or not expected or not hmac.compare_digest(supplied, expected):
            return JSONResponse({"detail": "Invalid control request token"}, status_code=403)

        try:
            principal = ControlSessionCodec(self.settings.control_session_secret).decode(token)
        except ValueError:
            return JSONResponse({"detail": "Control session expired"}, status_code=401)

        db = getattr(request.app.state, "db", None)
        if db is not None:
            async with db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT role,is_active FROM admin_users WHERE telegram_id=$1",
                    principal.telegram_id,
                )
            if row is not None:
                if not row["is_active"]:
                    return JSONResponse({"detail": "Admin access revoked"}, status_code=403)
                if row["role"] == "viewer":
                    return JSONResponse({"detail": "Viewer access is read-only"}, status_code=403)
            elif principal.telegram_id not in self.settings.admin_telegram_ids:
                return JSONResponse({"detail": "Admin access revoked"}, status_code=403)

        return await call_next(request)
