"""Pure weighting and aggregation functions for rolling football features."""

from collections.abc import Iterable


def recency_weight(*, age_days: int, half_life_days: float) -> float:
    """Return exponential half-life weight for a non-future observation."""
    if age_days < 0:
        raise ValueError("age_days cannot be negative")
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    return 0.5 ** (age_days / half_life_days)


def weighted_average(values: Iterable[tuple[float | None, float]]) -> float | None:
    """Average available observations without treating missing values as zero."""
    numerator = 0.0
    denominator = 0.0
    for value, weight in values:
        if value is None or weight <= 0:
            continue
        numerator += value * weight
        denominator += weight
    return numerator / denominator if denominator else None


def effective_sample_size(weights: Iterable[float]) -> float:
    """Return Kish effective sample size for unequal positive weights."""
    positive = [weight for weight in weights if weight > 0]
    if not positive:
        return 0.0
    total = sum(positive)
    return total * total / sum(weight * weight for weight in positive)
