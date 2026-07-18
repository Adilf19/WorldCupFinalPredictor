"""Pluggable evidence scorers for individual player matchups."""

from dataclasses import dataclass
from typing import Protocol

from database.models import Player


@dataclass(frozen=True, slots=True)
class ScoreEvidence:
    """Normalized home-side score and its supporting evidence."""

    home_advantage: float | None
    confidence: float
    evidence_dimensions: tuple[str, ...]
    missing_dimensions: tuple[str, ...]


class MatchupScorer(Protocol):
    """Interface implemented by attribute, H2H, and similarity scorers."""

    def score(
        self,
        *,
        home_player: Player,
        away_player: Player,
        home_profile: str,
        away_profile: str,
    ) -> ScoreEvidence:
        """Return a normalized advantage from the home team's perspective."""


@dataclass(frozen=True, slots=True)
class _ProfileValue:
    value: float | None
    coverage: float
    available: tuple[str, ...]
    missing: tuple[str, ...]


class AttributeMatchupScorer:
    """Baseline scorer using normalized 0-100 player attributes.

    This scorer is deliberately replaceable. Direct H2H and nearest-neighbour
    evidence can implement ``MatchupScorer`` without changing the positional
    predictor or its output contract.
    """

    _PROFILES: dict[str, dict[str, float]] = {
        "wing_attack": {
            "pace": 0.25,
            "dribbling": 0.30,
            "creativity": 0.20,
            "passing": 0.15,
            "finishing": 0.10,
        },
        "fullback_defense": {
            "defending": 0.45,
            "pace": 0.30,
            "strength": 0.25,
        },
        "striker_attack": {
            "finishing": 0.35,
            "strength": 0.20,
            "pace": 0.15,
            "dribbling": 0.15,
            "creativity": 0.15,
        },
        "centreback_defense": {
            "defending": 0.50,
            "strength": 0.30,
            "pace": 0.20,
        },
        "midfield": {
            "passing": 0.35,
            "creativity": 0.30,
            "dribbling": 0.15,
            "strength": 0.10,
            "defending": 0.10,
        },
        "defensive_midfield": {
            "defending": 0.35,
            "strength": 0.20,
            "passing": 0.25,
            "creativity": 0.10,
            "pace": 0.10,
        },
        # The current schema has no goalkeeper attributes. Keeping the profile
        # explicit makes this absence visible instead of inventing a proxy.
        "goalkeeper": {},
    }
    _GOALKEEPER_DIMENSIONS = ("reflexes", "handling", "aerial_control", "positioning")

    def __init__(self, *, attribute_scale: float = 100.0) -> None:
        if attribute_scale <= 0:
            raise ValueError("attribute_scale must be positive")
        self.attribute_scale = attribute_scale

    def score(
        self,
        *,
        home_player: Player,
        away_player: Player,
        home_profile: str,
        away_profile: str,
    ) -> ScoreEvidence:
        home = self._profile(home_player, home_profile, prefix="home")
        away = self._profile(away_player, away_profile, prefix="away")
        available = home.available + away.available
        missing = home.missing + away.missing
        if home.value is None or away.value is None:
            return ScoreEvidence(None, 0.0, available, missing)
        advantage = max(
            -1.0,
            min(1.0, (home.value - away.value) / self.attribute_scale),
        )
        return ScoreEvidence(
            home_advantage=advantage,
            confidence=min(home.coverage, away.coverage),
            evidence_dimensions=available,
            missing_dimensions=missing,
        )

    def _profile(self, player: Player, profile: str, *, prefix: str) -> _ProfileValue:
        if profile not in self._PROFILES:
            raise ValueError(f"Unknown matchup profile: {profile}")
        weights = self._PROFILES[profile]
        if not weights:
            missing = tuple(f"{prefix}.{name}" for name in self._GOALKEEPER_DIMENSIONS)
            return _ProfileValue(None, 0.0, (), missing)

        available: list[str] = []
        missing: list[str] = []
        weighted_total = 0.0
        available_weight = 0.0
        for attribute, weight in weights.items():
            value = getattr(player, attribute)
            dimension = f"{prefix}.{attribute}"
            if value is None:
                missing.append(dimension)
                continue
            available.append(dimension)
            weighted_total += float(value) * weight
            available_weight += weight
        coverage = available_weight / sum(weights.values())
        value = weighted_total / available_weight if coverage >= 0.5 else None
        return _ProfileValue(
            value=value,
            coverage=coverage,
            available=tuple(available),
            missing=tuple(missing),
        )
