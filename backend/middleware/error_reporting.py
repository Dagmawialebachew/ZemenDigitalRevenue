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
            response = await call_next(request)
        except Exception as exc:
            reporter = getattr(request.app.state, "error_reporter", None)
            context = self._context(request)
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

        # Some routes intentionally translate internal failures into safe 5xx
        # responses. They still need observability even though no exception escapes.
        if response.status_code >= 500:
            reporter = getattr(request.app.state, "error_reporter", None)
            if reporter is not None:
                failure = RuntimeError(
                    f"HTTP {response.status_code} from {request.method} {request.url.path}"
                )
                reporter.schedule(
                    failure,
                    surface="api_response",
                    context={**self._context(request), "status_code": response.status_code},
                )
        return response

    @staticmethod
    def _context(request: Request) -> dict[str, object]:
        return {
            "method": request.method,
            "path": request.url.path,
            "query_keys": ",".join(sorted(request.query_params.keys())) or "none",
        }
