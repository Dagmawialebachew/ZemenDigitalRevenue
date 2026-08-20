from __future__ import annotations

import random


def retry_delay_seconds(
    attempt: int,
    *,
    base_seconds: float = 2.0,
    cap_seconds: float = 900.0,
    jitter_ratio: float = 0.20,
    rng: random.Random | None = None,
) -> float:
    """Bounded exponential retry delay with symmetric jitter.

    `attempt` is one-based: attempt 1 backs off from base_seconds, attempt 2 from
    2*base_seconds, etc. Telegram's explicit retry_after always overrides this.
    """
    safe_attempt = max(1, int(attempt))
    raw = min(float(cap_seconds), float(base_seconds) * (2 ** (safe_attempt - 1)))
    if jitter_ratio <= 0:
        return raw
    source = rng or random
    jitter = raw * min(max(float(jitter_ratio), 0.0), 1.0)
    return max(0.0, min(float(cap_seconds), raw + source.uniform(-jitter, jitter)))
