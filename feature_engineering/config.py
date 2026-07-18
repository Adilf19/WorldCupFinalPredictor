"""Validated configuration for team feature generation."""

from pydantic import BaseModel, ConfigDict, Field


class TeamFeatureConfig(BaseModel):
    """Controls history selection, weighting, and confidence calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lookback_matches: int = Field(default=60, ge=1, le=150)
    lookback_days: int = Field(default=730, ge=30, le=1460)
    recency_half_life_days: float = Field(default=365.0, gt=0)
    default_competition_tier: float = Field(default=0.5, ge=0, le=1)
    minimum_competition_weight: float = Field(default=0.05, gt=0, le=1)
    full_confidence_matches: float = Field(default=20.0, gt=0)
