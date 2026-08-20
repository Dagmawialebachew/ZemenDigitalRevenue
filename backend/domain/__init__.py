"""Business-domain primitives for Zemen Digital.

Keep Telegram/FastAPI/UI concerns out of this package. These modules define the
rules that every interface must obey.
"""

from backend.domain.enums import (  # noqa: F401
    AutomationRunStatus,
    BroadcastStatus,
    CommissionStatus,
    CustomerStage,
    DeliveryStatus,
    JobStatus,
    OfferStatus,
    OrderStatus,
    PaymentStatus,
    PricingType,
)
