"""Validated configuration for lineup and positional matchup prediction."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictorConfig(BaseModel):
    """Shared formation and historical-evidence settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    formation_name: str = "4-3-3"
    formation_roles: tuple[str, ...] = (
        "GK",
        "RB",
        "RCB",
        "LCB",
        "LB",
        "DM",
        "RCM",
        "LCM",
        "RW",
        "ST",
        "LW",
    )
    lineup_lookback_matches: int = Field(default=12, ge=1, le=50)
    recency_half_life_days: float = Field(default=120.0, gt=0)
    full_evidence_appearances: float = Field(default=5.0, gt=0)
    spatial_grid_columns: int = Field(default=12, ge=4, le=30)
    spatial_grid_rows: int = Field(default=8, ge=3, le=20)
    spatial_lookback_matches: int = Field(default=20, ge=1, le=100)
    spatial_recency_half_life_days: float = Field(default=730.0, gt=0)
    spatial_full_evidence_events: int = Field(default=80, ge=1)
    spatial_minimum_events: int = Field(default=8, ge=1)
    # Partial licensed feeds are still valuable: surface covered players and
    # lower evidence coverage instead of discarding every available heatmap.
    spatial_minimum_lineup_coverage: float = Field(default=0.20, ge=0, le=1)
    h2h_recency_half_life_days: float = Field(default=730.0, gt=0)
    h2h_full_evidence_matches: int = Field(default=4, ge=1)
    h2h_similarity_fallback_confidence: float = Field(default=0.5, ge=0, le=1)
    similarity_neighbors: int = Field(default=5, ge=1, le=20)
    similarity_minimum_events: int = Field(default=20, ge=1)
    similarity_minimum_score: float = Field(default=0.35, ge=0, le=1)

    @model_validator(mode="after")
    def validate_formation(self) -> "PredictorConfig":
        if len(self.formation_roles) != 11:
            raise ValueError("formation_roles must contain exactly 11 roles")
        if len(set(self.formation_roles)) != 11:
            raise ValueError("formation_roles must be unique")
        if "GK" not in self.formation_roles:
            raise ValueError("formation_roles must contain GK")
        return self
