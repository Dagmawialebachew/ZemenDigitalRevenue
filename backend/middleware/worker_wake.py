from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class WorkerWakeMiddleware(BaseHTTPMiddleware):
    """Wake idle workers after request-driven transactions have committed.

    Health probes and static assets deliberately do not wake workers or PostgreSQL.
    This lets a scale-to-zero database suspend while the Render web process remains
    reachable. Durable scheduled jobs are still found by the fallback poll.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") or path == "/telegram/webhook":
            workers = getattr(request.app.state, "workers", None)
            if workers is not None:
                workers.wake()
        return response
