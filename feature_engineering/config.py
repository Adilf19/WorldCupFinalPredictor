"""Validated configuration for team feature generation."""

from pydantic import BaseModel, ConfigDict, Field


class TeamFeatureConfig(BaseModel):
    """Controls history selection, weighting, and confidence calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lookback_matches: int = Field(default=20, ge=1, le=100)
    recency_half_life_days: float = Field(default=180.0, gt=0)
    default_competition_tier: float = Field(default=0.5, ge=0, le=1)
    minimum_competition_weight: float = Field(default=0.05, gt=0, le=1)
    full_confidence_matches: float = Field(default=10.0, gt=0)
