from shared.deeplinks import StartKind, parse_start_payload


def test_source_token() -> None:
    value = parse_start_payload("src_X7K3")
    assert value.kind == StartKind.SOURCE
    assert value.token == "X7K3"


def test_referral_token() -> None:
    value = parse_start_payload("ref_8GQ29")
    assert value.kind == StartKind.REFERRAL
    assert value.token == "8GQ29"


def test_rejects_unsafe_payload() -> None:
    value = parse_start_payload("src_<script>")
    assert value.kind == StartKind.UNKNOWN
    assert value.token is None


def test_order_handoff_token() -> None:
    value = parse_start_payload("ord_ZD-1234567890")
    assert value.kind == StartKind.ORDER
    assert value.token == "ZD-1234567890"
