import pytest

from backend.domain.enums import OrderStatus, PaymentStatus
from backend.domain.errors import InvalidStateTransition
from backend.domain.states import ORDER_TRANSITIONS, PAYMENT_TRANSITIONS, ensure_transition


def test_order_happy_path_transition() -> None:
    ensure_transition(OrderStatus.CREATED, OrderStatus.AWAITING_PAYMENT, ORDER_TRANSITIONS)
    ensure_transition(OrderStatus.AWAITING_PAYMENT, OrderStatus.PROOF_SUBMITTED, ORDER_TRANSITIONS)
    ensure_transition(OrderStatus.PROOF_SUBMITTED, OrderStatus.UNDER_REVIEW, ORDER_TRANSITIONS)
    ensure_transition(OrderStatus.UNDER_REVIEW, OrderStatus.PAID, ORDER_TRANSITIONS)


def test_paid_order_cannot_return_to_pending() -> None:
    with pytest.raises(InvalidStateTransition):
        ensure_transition(OrderStatus.PAID, OrderStatus.AWAITING_PAYMENT, ORDER_TRANSITIONS)


def test_rejected_payment_can_be_resubmitted() -> None:
    ensure_transition(PaymentStatus.REJECTED, PaymentStatus.PENDING_REVIEW, PAYMENT_TRANSITIONS)
