"""Versioned lineup and positional-matchup prediction contracts."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PredictionContract(BaseModel):
    """Strict immutable base for matchup-engine outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PredictedLineupPlayer(PredictionContract):
    """One player selected into a predicted formation role."""

    player_id: int
    player_name: str
    photo_url: str | None = None
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    assigned_role: str
    primary_position: str | None = None
    secondary_position: str | None = None
    selection_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    weighted_appearances: float = Field(ge=0)
    weighted_starts: float = Field(ge=0)
    weighted_minutes: float = Field(ge=0)
    club_form: float | None = Field(default=None, ge=0, le=1)
    country_form: float | None = Field(default=None, ge=0, le=1)
    blended_form: float | None = Field(default=None, ge=0, le=1)
    form_coverage: float = Field(default=0, ge=0, le=1)


class PredictedLineup(PredictionContract):
    """An expected starting lineup with evidence and completeness metadata."""

    prediction_version: str = "lineup_v1"
    team_id: int
    team_name: str
    as_of: date
    formation: str
    players: tuple[PredictedLineupPlayer, ...]
    completeness: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    warnings: tuple[str, ...] = ()

    def player_for_role(self, role: str) -> PredictedLineupPlayer | None:
        """Return the selected player for a formation role."""
        return next((player for player in self.players if player.assigned_role == role), None)


class HeatmapGrid(PredictionContract):
    """UI-ready player action density in attacking-direction coordinates."""

    columns: int = Field(ge=1)
    rows: int = Field(ge=1)
    cells: tuple[float, ...]
    sample_events: int = Field(ge=0)
    sample_matches: int = Field(ge=0)
    source: str = "statsbomb_open"
    measure: str = "recency_weighted_on_ball_actions"
    orientation: str = "attacking_left_to_right"


class MatchupEvidenceSummary(PredictionContract):
    """An auditable component contributing to one combined battle score."""

    source: str
    home_advantage: float | None = Field(default=None, ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    sample_matches: int = Field(ge=0)
    sample_minutes: float = Field(ge=0)
    analogous_players: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    explanation: str


class BattlePrediction(PredictionContract):
    """One directional on-pitch player battle from the home perspective."""

    label: str
    home_role: str
    away_role: str
    home_player: PredictedLineupPlayer | None
    away_player: PredictedLineupPlayer | None
    home_advantage: float | None = Field(default=None, ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    weight: float = Field(gt=0)
    evidence_dimensions: tuple[str, ...] = ()
    missing_dimensions: tuple[str, ...] = ()
    explanation: str
    method: str = "positional_attributes"
    spatial_overlap: float | None = Field(default=None, ge=0, le=1)
    home_heatmap: HeatmapGrid | None = None
    away_heatmap: HeatmapGrid | None = None
    direct_h2h: MatchupEvidenceSummary | None = None
    similarity_evidence: MatchupEvidenceSummary | None = None


class MatchupPrediction(PredictionContract):
    """Predicted lineups and all important positional battles."""

    prediction_version: str = "positional_matchups_v1"
    as_of: date
    home_lineup: PredictedLineup
    away_lineup: PredictedLineup
    battles: tuple[BattlePrediction, ...]
    overall_home_advantage: float | None = Field(default=None, ge=-1, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    biggest_differentiator: str | None = None
    warnings: tuple[str, ...] = ()
    matchup_method: str = "positional_attributes"
