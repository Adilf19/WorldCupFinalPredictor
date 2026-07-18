"""Public and owner-only HTTP request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class RequestCodeBody(ApiSchema):
    email: EmailStr


class VerifyCodeBody(ApiSchema):
    email: EmailStr
    code: str = Field(pattern=r"^\d{4}$")


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


class SelectFixtureBody(FixtureCandidate):
    external_id: str = ""


class ActiveFixture(FixtureCandidate):
    id: int
    status: str
    is_active: bool


class PublicPrediction(ApiSchema):
    model_version: str
    expected_goals_home: float
    expected_goals_away: float
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    home_qualification_probability: float
    away_qualification_probability: float
    extra_time_probability: float
    penalties_probability: float
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


class LiveResponse(ApiSchema):
    status: str
    minute: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    events: list[dict[str, Any]] = []
