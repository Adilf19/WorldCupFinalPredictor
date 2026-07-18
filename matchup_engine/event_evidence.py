"""Shared action-quality calculations for matchup evidence engines."""

from collections.abc import Iterable

from database.models import SpatialEvent

ACTION_VALUE = {
    "Shot": 1.0,
    "Dribble": 0.85,
    "Carry": 0.72,
    "Pass": 0.68,
    "Ball Recovery": 0.72,
    "Interception": 0.82,
    "Duel": 0.76,
    "Clearance": 0.62,
    "Block": 0.72,
    "Pressure": 0.55,
}
FAILED_OUTCOMES = {"Incomplete", "Out", "Blocked", "Lost", "Lost In Play", "No Touch"}


def action_quality(event: SpatialEvent) -> float:
    """Return a bounded action value without treating missing outcomes as failure."""
    value = ACTION_VALUE.get(event.event_type, 0.5)
    if event.outcome in FAILED_OUTCOMES:
        value *= 0.25
    if event.under_pressure:
        value *= 1.05
    return min(1.0, value)


def mean_action_quality(events: Iterable[SpatialEvent]) -> float | None:
    values = [action_quality(event) for event in events]
    return sum(values) / len(values) if values else None


def normalized_advantage(home: float, away: float) -> float:
    return max(-1.0, min(1.0, (home - away) / max(0.1, home + away)))
