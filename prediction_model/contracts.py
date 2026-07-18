"""Validated contracts for model training and goal-rate inference."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoalRatePrediction(ModelContract):
    model_version: str
    as_of: date
    home_team_id: int
    away_team_id: int
    expected_goals_home: float = Field(ge=0)
    expected_goals_away: float = Field(ge=0)
    feature_coverage: float = Field(ge=0, le=1)


class ValidationMetrics(ModelContract):
    rows: int = Field(ge=1)
    start_date: date
    end_date: date
    home_goal_mae: float = Field(ge=0)
    away_goal_mae: float = Field(ge=0)
    combined_goal_mae: float = Field(ge=0)
    home_poisson_deviance: float = Field(ge=0)
    away_poisson_deviance: float = Field(ge=0)


class TrainingReport(ModelContract):
    model_version: str
    artifact_directory: str
    dataset_rows: int = Field(ge=1)
    training_rows: int = Field(ge=1)
    validation: ValidationMetrics
    feature_count: int = Field(ge=1)
    feature_names: tuple[str, ...]
    best_iterations: dict[str, int]
    trained_through: date
    limitations: tuple[str, ...]
