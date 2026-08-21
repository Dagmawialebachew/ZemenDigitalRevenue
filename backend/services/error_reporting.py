from __future__ import annotations

import asyncio
import hashlib
import re
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from html import escape
from time import monotonic
from typing import Any

import structlog
from aiogram import Bot

from backend.core.config import Settings

log = structlog.get_logger(__name__)

_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(token|authorization|password|secret|api[_ -]?key|owner[_ -]?key)"
        r"\s*[=:]\s*\S+"
    ),
    re.compile(r"(?i)postgres(?:ql)?://[^\s]+"),
    re.compile(r"(?i)https?://[^\s/:]+:[^\s/@]+@[^\s]+"),
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{25,}\b"),
)
_tasks: set[asyncio.Task[Any]] = set()


def _safe_text(value: object, *, limit: int = 500) -> str:
    text = str(value).replace("\x00", "").strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if len(text) > limit:
        text = f"{text[: limit - 1]}…"
    return text


class ErrorReporter:
    """Send bounded, sanitized runtime diagnostics to the private Errors topic."""

    def __init__(self, *, bot: Bot, settings: Settings, dedupe_seconds: float = 300.0) -> None:
        self.bot = bot
        self.group_id = settings.zemen_ops_group_id
        self.topic_id = settings.zemen_ops_topic_errors
        self.dedupe_seconds = dedupe_seconds
        self._last_sent: dict[str, float] = {}
        self._suppressed: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.group_id and self.topic_id)

    def schedule(
        self,
        exception: BaseException,
        *,
        surface: str,
        context: Mapping[str, object] | None = None,
    ) -> str:
        """Queue a report without delaying the customer response; return its reference."""
        reference = self.reference(exception, surface=surface)
        if not self.enabled:
            return reference
        task = asyncio.create_task(
            self.report(exception, surface=surface, context=context, reference=reference),
            name=f"error-report-{reference.lower()}",
        )
        _tasks.add(task)

        def finished(completed: asyncio.Task[Any]) -> None:
            _tasks.discard(completed)
            try:
                completed.result()
            except asyncio.CancelledError:
                return
            except Exception:
                # Never report errors from the reporter back through itself.
                log.exception("error_report_task_failed", reference=reference)

        task.add_done_callback(finished)
        return reference

    def reference(self, exception: BaseException, *, surface: str) -> str:
        frames = traceback.extract_tb(exception.__traceback__)
        location = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else "unknown"
        raw = f"{surface}|{type(exception).__name__}|{_safe_text(exception)}|{location}"
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:8].upper()

    async def report(
        self,
        exception: BaseException,
        *,
        surface: str,
        context: Mapping[str, object] | None = None,
        reference: str | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        reference = reference or self.reference(exception, surface=surface)
        now = monotonic()
        previous = self._last_sent.get(reference)
        if previous is not None and now - previous < self.dedupe_seconds:
            self._suppressed[reference] = self._suppressed.get(reference, 0) + 1
            return False

        repeated = self._suppressed.pop(reference, 0)
        self._last_sent[reference] = now
        if len(self._last_sent) > 256:
            oldest = min(self._last_sent, key=self._last_sent.__getitem__)
            self._last_sent.pop(oldest, None)
            self._suppressed.pop(oldest, None)

        lines = [
            "🚨 <b>ZEMEN RUNTIME ERROR</b>",
            "",
            f"<b>Surface:</b> <code>{escape(_safe_text(surface, limit=80))}</code>",
            f"<b>Type:</b> <code>{escape(type(exception).__name__)}</code>",
            f"<b>Error:</b> {escape(_safe_text(exception)) or '[no message]'}",
            f"<b>Reference:</b> <code>{reference}</code>",
            f"<b>Time:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        if repeated:
            lines.append(f"<b>Repeated:</b> {repeated} similar error(s) suppressed")
        if context:
            lines.extend(("", "<b>Context</b>"))
            for key, value in list(context.items())[:10]:
                safe_key = escape(_safe_text(key, limit=40))
                safe_value = escape(_safe_text(value, limit=180))
                lines.append(f"• <b>{safe_key}:</b> <code>{safe_value}</code>")

        frames = traceback.extract_tb(exception.__traceback__)
        if frames:
            lines.extend(("", "<b>Trace</b>"))
            for frame in frames[-4:]:
                filename = frame.filename.replace("\\", "/").rsplit("/", 2)[-1]
                trace_line = f"{filename}:{frame.lineno} in {frame.name}"
                lines.append(f"<code>{escape(_safe_text(trace_line, limit=180))}</code>")

        try:
            await self.bot.send_message(
                chat_id=self.group_id,
                message_thread_id=self.topic_id,
                text="\n".join(lines)[:4096],
            )
            return True
        except Exception:
            # Never recurse: a failed error notification is logged only.
            log.exception("error_topic_notification_failed", reference=reference)
            return False
