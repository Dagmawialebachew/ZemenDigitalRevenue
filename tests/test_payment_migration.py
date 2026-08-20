from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_s07_payment_migration_has_review_and_race_guards() -> None:
    sql = (ROOT / "database/migrations/0007_manual_payments.sql").read_text(encoding="utf-8")
    for token in (
        "latest_proof_id",
        "active_order_id",
        "active_payment_id",
        "payment_review_messages",
        "idx_payment_proofs_unique_file",
        "enforce_payment_expected_amount",
        "uq_live_payment_per_order",
    ):
        assert token in sql


def test_review_message_is_bound_to_exact_proof() -> None:
    sql = (ROOT / "database/migrations/0007_manual_payments.sql").read_text(encoding="utf-8")
    assert "proof_id UUID NOT NULL REFERENCES payment_proofs(id)" in sql
    assert "UNIQUE (ops_chat_id, ops_message_id)" in sql
