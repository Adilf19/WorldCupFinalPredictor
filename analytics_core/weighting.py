"""Shared time-weighting primitives."""


def recency_weight(*, age_days: int, half_life_days: float) -> float:
    """Return exponential half-life weight for a non-future observation."""
    if age_days < 0:
        raise ValueError("age_days cannot be negative")
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    return 0.5 ** (age_days / half_life_days)
