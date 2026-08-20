from __future__ import annotations

import random

from workers.backoff import retry_delay_seconds


def test_backoff_without_jitter_is_exponential_and_capped() -> None:
    assert retry_delay_seconds(1, base_seconds=2, cap_seconds=10, jitter_ratio=0) == 2
    assert retry_delay_seconds(2, base_seconds=2, cap_seconds=10, jitter_ratio=0) == 4
    assert retry_delay_seconds(3, base_seconds=2, cap_seconds=10, jitter_ratio=0) == 8
    assert retry_delay_seconds(4, base_seconds=2, cap_seconds=10, jitter_ratio=0) == 10


def test_backoff_jitter_stays_bounded() -> None:
    rng = random.Random(42)
    values = [
        retry_delay_seconds(3, base_seconds=5, cap_seconds=60, jitter_ratio=0.2, rng=rng)
        for _ in range(100)
    ]
    assert all(16 <= value <= 24 for value in values)
