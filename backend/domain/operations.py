from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DeliveryAttemptStatus(StrEnum):
    STARTED = "started"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"
    DEDUPED = "deduped"


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    scanned: int
    requeued: int
    skipped: int


@dataclass(frozen=True, slots=True)
class SupportCaseRef:
    id: UUID
    public_id: str
    status: str
