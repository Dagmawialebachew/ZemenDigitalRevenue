from pathlib import Path


def test_after_language_can_continue_known_ad_angle():
    text = Path("bot/services/copy.py").read_text(encoding="utf-8")
    assert "beginner_confusion" in text
    assert "work_study_business" in text
    assert "_angle_hint" in text
