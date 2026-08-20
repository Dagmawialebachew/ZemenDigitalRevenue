from pathlib import Path


def test_database_pool_registers_native_json_codecs():
    text = Path("backend/db/pool.py").read_text(encoding="utf-8")
    assert 'set_type_codec(' in text
    assert '"jsonb"' in text
    assert 'init=_init_connection' in text
