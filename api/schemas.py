"""Public and owner-only HTTP request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class OwnerLoginBody(ApiSchema):
    password: str = Field(min_length=8, max_length=256)


class FixtureCandidate(ApiSchema):
    provider: str
    external_id: str
    home_name: str
    away_name: str
    kickoff_at: datetime
    match_id: int | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    timing_accuracy: str = "exact"
    competition_id: int | None = None
    competition_name: str | None = None
    competition_format: str = "league"
    home_logo_url: str | None = None
    away_logo_url: str | None = None
    home_manager: str | None = None
    away_manager: str | None = None
    home_manager_photo_url: str | None = None
    away_manager_photo_url: str | None = None


class CompetitionCandidate(ApiSchema):
    provider: str
    external_id: str
    code: str | None = None
    name: str
    country: str | None = None
    format: str
    team_type: str
    current_season: int | None = None


class SyncCompetitionBody(ApiSchema):
    competition: str = Field(min_length=1, max_length=20)
    seasons: list[int] = Field(min_length=1, max_length=2)


class SelectFixtureBody(FixtureCandidate):
    external_id: str = ""


class ActiveFixture(FixtureCandidate):
    id: int
    status: str
    is_active: bool


class PublicPrediction(ApiSchema):
    model_version: str
    match_format: str
    expected_goals_home: float
    expected_goals_away: float
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    home_qualification_probability: float | None = None
    away_qualification_probability: float | None = None
    extra_time_probability: float | None = None
    penalties_probability: float | None = None
    projected_home_goals: int
    projected_away_goals: int
    model_inputs: dict[str, float | int | None]
    top_feature_importance: dict[str, list[tuple[str, float]]]


class PublicMatchups(ApiSchema):
    average_confidence: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    overall_home_advantage: float | None
    evidence_scope: str
    club_h2h_available: bool
    battles: list[dict[str, Any]]
    warnings: list[str]


class LineupResponse(ApiSchema):
    mode: str
    provider_status: str
    home: list[dict[str, Any]]
    away: list[dict[str, Any]]
    predicted_home: list[dict[str, Any]]
    predicted_away: list[dict[str, Any]]
    actual_home: list[dict[str, Any]]
    actual_away: list[dict[str, Any]]
    actual_status: str


class LiveResponse(ApiSchema):
    status: str
    minute: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    events: list[dict[str, Any]] = []
