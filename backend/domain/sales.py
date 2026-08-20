from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.domain.enums import AIExperience, MainGoal, MainObstacle, UserRole

PROFILE_FIELDS: tuple[str, ...] = ("role", "ai_experience", "main_goal", "main_obstacle")

_ALLOWED: Mapping[str, frozenset[str]] = {
    "role": frozenset(item.value for item in UserRole),
    "ai_experience": frozenset(item.value for item in AIExperience),
    "main_goal": frozenset(item.value for item in MainGoal),
    "main_obstacle": frozenset(item.value for item in MainObstacle),
}

SIGNAL_WEIGHTS: Mapping[str, int] = {
    "ONBOARDING_COMPLETED": 20,
    "SALES_PITCH_VIEWED": 10,
    "PREVIEW_VIEWED": 20,
    "OBJECTION_OPENED": 10,
    "BUY_CLICKED": 40,
}


@dataclass(frozen=True, slots=True)
class SalesProfile:
    role: str | None = None
    ai_experience: str | None = None
    main_goal: str | None = None
    main_obstacle: str | None = None

    @property
    def complete(self) -> bool:
        return all(getattr(self, field) for field in PROFILE_FIELDS)


@dataclass(frozen=True, slots=True)
class JourneySignalResult:
    score: int
    stage: str


def validate_profile_answer(field: str, value: str) -> None:
    if field not in _ALLOWED:
        raise ValueError(f"unsupported onboarding field: {field}")
    if value not in _ALLOWED[field]:
        raise ValueError(f"unsupported {field} value: {value}")


def next_unanswered_profile_field(profile: SalesProfile) -> str | None:
    for field in PROFILE_FIELDS:
        if not getattr(profile, field):
            return field
    return None


def audience_keys(profile: SalesProfile, *, angle: str | None = None) -> list[str]:
    """Most-specific first. Dashboard-authored content can target any of these."""
    keys: list[str] = []
    pieces = []
    if profile.role:
        pieces.append(f"role:{profile.role}")
    if profile.ai_experience:
        pieces.append(f"exp:{profile.ai_experience}")
    if profile.main_goal:
        pieces.append(f"goal:{profile.main_goal}")
    if profile.main_obstacle:
        pieces.append(f"obstacle:{profile.main_obstacle}")
    if angle:
        pieces.append(f"angle:{angle}")

    if pieces:
        keys.append("|".join(pieces))
    if angle:
        keys.append(f"angle:{angle}")
    if profile.main_obstacle:
        keys.append(f"obstacle:{profile.main_obstacle}")
    if profile.role:
        keys.append(f"role:{profile.role}")
    if profile.ai_experience:
        keys.append(f"exp:{profile.ai_experience}")
    if profile.main_goal:
        keys.append(f"goal:{profile.main_goal}")
    keys.append("default")

    # De-duplicate while preserving priority.
    return list(dict.fromkeys(keys))


def score_after_signal(
    current_score: int,
    signal_key: str,
    *,
    current_stage: str = "introduced",
) -> JourneySignalResult:
    """Apply an intent signal without allowing terminal sales intent to regress."""
    delta = SIGNAL_WEIGHTS.get(signal_key, 0)
    score = max(0, min(100, current_score + delta))
    if current_stage == "buy_clicked" or signal_key == "BUY_CLICKED":
        stage = "buy_clicked"
    elif score >= 60:
        stage = "high_intent"
    elif score >= 35:
        stage = "interested"
    elif score >= 10:
        stage = "exploring"
    else:
        stage = "introduced"
    return JourneySignalResult(score=score, stage=stage)
