from backend.domain.enums import CustomerStage, PaymentRejectReason


def test_customer_stage_values_are_stable() -> None:
    assert CustomerStage.HIGH_INTENT.value == "high_intent"
    assert CustomerStage.CUSTOMER.value == "customer"


def test_payment_rejection_reasons_are_machine_readable() -> None:
    assert PaymentRejectReason.DUPLICATE_RECEIPT.value == "duplicate_receipt"
