from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from .enums import (
    AIExperience,
    CommissionStatus,
    CustomerStage,
    DeliveryStatus,
    LanguageCode,
    OfferStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ProductStatus,
    UserRole,
)


@dataclass(frozen=True, slots=True)
class User:
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language: LanguageCode | None
    stage: CustomerStage
    is_blocked: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: int
    role: UserRole | None
    ai_experience: AIExperience | None
    main_goal: str | None
    main_obstacle: str | None
    onboarding_completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class Product:
    id: int
    public_id: str
    slug: str
    status: ProductStatus
    regular_price: Decimal
    recovery_price: Decimal | None
    discount_enabled: bool
    referral_enabled: bool
    referral_commission_percent: Decimal
    featured: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Order:
    id: int
    public_id: str
    user_id: int
    product_id: int
    status: OrderStatus
    currency: str
    list_price: Decimal
    amount_due: Decimal
    discount_amount: Decimal
    customer_offer_id: int | None
    referral_attribution_id: int | None
    commissionable: bool
    created_at: datetime
    paid_at: datetime | None


@dataclass(frozen=True, slots=True)
class Payment:
    id: int
    public_id: str
    order_id: int
    method: PaymentMethod
    status: PaymentStatus
    expected_amount: Decimal
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None


@dataclass(frozen=True, slots=True)
class Entitlement:
    id: int
    user_id: int
    product_id: int
    order_id: int
    delivery_status: DeliveryStatus
    granted_at: datetime


@dataclass(frozen=True, slots=True)
class CustomerOffer:
    id: int
    user_id: int
    product_id: int
    price: Decimal
    status: OfferStatus
    eligible_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class Commission:
    id: int
    beneficiary_user_id: int
    order_id: int
    amount: Decimal
    rate_percent: Decimal
    status: CommissionStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DomainEvent:
    id: int
    user_id: int | None
    event_type: str
    product_id: int | None
    order_id: int | None
    source_link_id: int | None
    properties: dict[str, Any]
    created_at: datetime
