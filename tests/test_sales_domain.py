from backend.domain.sales import (
    SalesProfile,
    audience_keys,
    next_unanswered_profile_field,
    score_after_signal,
    validate_profile_answer,
)


def test_four_step_onboarding_order():
    p = SalesProfile()
    assert next_unanswered_profile_field(p) == "role"
    p = SalesProfile(role="student")
    assert next_unanswered_profile_field(p) == "ai_experience"
    p = SalesProfile(role="student", ai_experience="tried_confused")
    assert next_unanswered_profile_field(p) == "main_goal"
    p = SalesProfile(role="student", ai_experience="tried_confused", main_goal="learn_faster")
    assert next_unanswered_profile_field(p) == "main_obstacle"
    p = SalesProfile(
        role="student",
        ai_experience="tried_confused",
        main_goal="learn_faster",
        main_obstacle="dont_know_what_to_ask",
    )
    assert next_unanswered_profile_field(p) is None
    assert p.complete


def test_profile_validation_rejects_unknown_value():
    validate_profile_answer("role", "student")
    try:
        validate_profile_answer("role", "spaceship_captain")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown role must be rejected")


def test_audience_keys_are_specific_then_fallback():
    p = SalesProfile(
        role="student",
        ai_experience="tried_confused",
        main_goal="learn_faster",
        main_obstacle="dont_know_what_to_ask",
    )
    keys = audience_keys(p, angle="beginner_confusion")
    assert keys[0].startswith("role:student|exp:tried_confused")
    assert "angle:beginner_confusion" in keys
    assert keys[-1] == "default"


def test_intent_scoring_is_bounded_and_buy_click_wins_stage():
    score = 0
    for signal in ["ONBOARDING_COMPLETED", "SALES_PITCH_VIEWED", "PREVIEW_VIEWED", "OBJECTION_OPENED"]:
        result = score_after_signal(score, signal)
        score = result.score
    assert score == 60
    assert result.stage == "high_intent"
    result = score_after_signal(score, "BUY_CLICKED")
    assert result.score == 100
    assert result.stage == "buy_clicked"


def test_buy_clicked_stage_does_not_regress_after_later_signal():
    result = score_after_signal(80, "PREVIEW_VIEWED", current_stage="buy_clicked")
    assert result.score == 100
    assert result.stage == "buy_clicked"
