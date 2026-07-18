"""Versioned outputs produced by the team feature pipeline."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class FeatureContract(BaseModel):
    """Strict immutable base for model feature contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TeamFeatureVector(FeatureContract):
    """Explainable, model-ready rolling features for one team."""

    feature_version: str = "team_features_v1"
    team_id: int
    team_name: str
    as_of: date
    matches_considered: int = Field(ge=0)
    effective_sample_size: float = Field(ge=0)
    total_weight: float = Field(ge=0)

    win_rate: float | None = Field(default=None, ge=0, le=1)
    draw_rate: float | None = Field(default=None, ge=0, le=1)
    loss_rate: float | None = Field(default=None, ge=0, le=1)
    points_per_match: float | None = Field(default=None, ge=0, le=3)
    goals_for: float | None = Field(default=None, ge=0)
    goals_against: float | None = Field(default=None, ge=0)
    goal_difference: float | None = None
    xg_for: float | None = Field(default=None, ge=0)
    xg_against: float | None = Field(default=None, ge=0)
    xg_difference: float | None = None
    possession: float | None = Field(default=None, ge=0, le=100)
    shots_for: float | None = Field(default=None, ge=0)
    shots_against: float | None = Field(default=None, ge=0)
    pass_accuracy: float | None = Field(default=None, ge=0, le=100)
    clean_sheet_rate: float | None = Field(default=None, ge=0, le=1)
    scoring_rate: float | None = Field(default=None, ge=0, le=1)
    home_match_share: float | None = Field(default=None, ge=0, le=1)

    elo_rating: float | None = None
    fifa_ranking: int | None = Field(default=None, ge=1)
    playing_style: str | None = None
    manager: str | None = None

    statistics_coverage: float = Field(ge=0, le=1)
    sample_confidence: float = Field(ge=0, le=1)

    def model_features(self, *, prefix: str) -> dict[str, float | int | None]:
        """Return stable numeric fields for a downstream model matrix."""
        numeric_fields = (
            "matches_considered",
            "effective_sample_size",
            "win_rate",
            "draw_rate",
            "loss_rate",
            "points_per_match",
            "goals_for",
            "goals_against",
            "goal_difference",
            "xg_for",
            "xg_against",
            "xg_difference",
            "possession",
            "shots_for",
            "shots_against",
            "pass_accuracy",
            "clean_sheet_rate",
            "scoring_rate",
            "home_match_share",
            "elo_rating",
            "fifa_ranking",
            "statistics_coverage",
            "sample_confidence",
        )
        return {f"{prefix}_{field}": getattr(self, field) for field in numeric_fields}


class TeamFeatureDeltas(FeatureContract):
    """Home-minus-away differences used as matchup-level model inputs."""

    points_per_match: float | None = None
    goal_difference: float | None = None
    xg_difference: float | None = None
    possession: float | None = None
    shots_for: float | None = None
    pass_accuracy: float | None = None
    elo_rating: float | None = None
    fifa_rank_advantage: float | None = None


class TeamFeatureComparison(FeatureContract):
    """Two team vectors and their directional matchup deltas."""

    feature_version: str = "team_comparison_v1"
    as_of: date
    home: TeamFeatureVector
    away: TeamFeatureVector
    deltas: TeamFeatureDeltas

    def model_features(self) -> dict[str, float | int | None]:
        """Flatten both vectors and deltas into a deterministic feature row."""
        values = self.home.model_features(prefix="home")
        values.update(self.away.model_features(prefix="away"))
        values.update(
            {
                f"delta_{field}": value
                for field, value in self.deltas.model_dump().items()
            }
        )
        return values
