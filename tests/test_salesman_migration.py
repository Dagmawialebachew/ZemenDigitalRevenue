from pathlib import Path


def test_s05_migration_has_multi_product_journey_and_unique_signals():
    text = Path("database/migrations/0006_salesman_personalization.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE user_product_journeys" in text
    assert "PRIMARY KEY (user_id, product_id)" in text
    assert "CREATE TABLE user_product_signals" in text
    assert "UNIQUE (user_id, product_id, signal_key)" in text
    assert "idx_product_content_blocks_lookup" in text
