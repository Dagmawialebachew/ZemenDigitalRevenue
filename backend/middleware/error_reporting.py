from __future__ import annotations

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)


class ErrorReportingMiddleware(BaseHTTPMiddleware):
    """Report unexpected API failures without collecting request bodies or secrets."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        try:
            return await call_next(request)
        except Exception as exc:
            reporter = getattr(request.app.state, "error_reporter", None)
            context = {
                "method": request.method,
                "path": request.url.path,
                "query_keys": ",".join(sorted(request.query_params.keys())) or "none",
            }
            reference = "UNAVAILABLE"
            if reporter is not None:
                reference = reporter.schedule(exc, surface="api", context=context)
            log.exception("unhandled_api_error", reference=reference, **context)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Something went wrong. Zemen support has been notified.",
                    "reference": reference,
                },
            )
