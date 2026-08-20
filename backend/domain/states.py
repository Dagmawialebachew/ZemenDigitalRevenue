from __future__ import annotations

from enum import StrEnum
from typing import Mapping, TypeVar

from backend.domain.enums import OfferStatus, OrderStatus, PaymentStatus
from backend.domain.errors import InvalidStateTransition

E = TypeVar("E", bound=StrEnum)

ORDER_TRANSITIONS: Mapping[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.AWAITING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.AWAITING_PAYMENT: frozenset({
        OrderStatus.PROOF_SUBMITTED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    }),
    OrderStatus.PROOF_SUBMITTED: frozenset({OrderStatus.UNDER_REVIEW}),
    OrderStatus.UNDER_REVIEW: frozenset({OrderStatus.NEEDS_NEW_PROOF, OrderStatus.PAID}),
    OrderStatus.NEEDS_NEW_PROOF: frozenset({
        OrderStatus.PROOF_SUBMITTED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    }),
    OrderStatus.PAID: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}

PAYMENT_TRANSITIONS: Mapping[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.AWAITING_PROOF: frozenset({PaymentStatus.PENDING_REVIEW, PaymentStatus.CANCELLED}),
    PaymentStatus.PENDING_REVIEW: frozenset({
        PaymentStatus.APPROVED,
        PaymentStatus.REJECTED,
        PaymentStatus.FLAGGED,
    }),
    PaymentStatus.FLAGGED: frozenset({PaymentStatus.APPROVED, PaymentStatus.REJECTED}),
    PaymentStatus.REJECTED: frozenset({PaymentStatus.PENDING_REVIEW, PaymentStatus.CANCELLED}),
    PaymentStatus.APPROVED: frozenset(),
    PaymentStatus.CANCELLED: frozenset(),
}

OFFER_TRANSITIONS: Mapping[OfferStatus, frozenset[OfferStatus]] = {
    OfferStatus.SCHEDULED: frozenset({OfferStatus.AVAILABLE, OfferStatus.REVOKED, OfferStatus.EXPIRED}),
    OfferStatus.AVAILABLE: frozenset({OfferStatus.REDEEMED, OfferStatus.REVOKED, OfferStatus.EXPIRED}),
    OfferStatus.REDEEMED: frozenset(),
    OfferStatus.EXPIRED: frozenset(),
    OfferStatus.REVOKED: frozenset(),
}


def ensure_transition(current: E, target: E, transitions: Mapping[E, frozenset[E]]) -> None:
    if target not in transitions.get(current, frozenset()):
        raise InvalidStateTransition(f"Invalid transition: {current} -> {target}")
