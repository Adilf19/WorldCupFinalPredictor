"""Combined lineup and positional-matchup prediction pipeline."""

from datetime import date

from sqlalchemy.orm import Session

from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupPrediction
from matchup_engine.lineup_predictor import LineupPredictor
from matchup_engine.matchup_scorer import MatchupScorer
from matchup_engine.positional_matchup import PositionalMatchupPredictor
from matchup_engine.spatial_matchup import SpatialMatchupPredictor


class MatchupPredictionPipeline:
    """Predict both lineups, then evaluate their important positional battles."""

    def __init__(
        self,
        session: Session,
        *,
        config: PredictorConfig | None = None,
        scorer: MatchupScorer | None = None,
    ) -> None:
        resolved_config = config or PredictorConfig()
        self.lineups = LineupPredictor(session, config=resolved_config)
        self.matchups = PositionalMatchupPredictor(session, scorer=scorer)
        self.spatial_matchups = SpatialMatchupPredictor(session, config=resolved_config)

    def predict(
        self, *, home_team_id: int, away_team_id: int, as_of: date
    ) -> MatchupPrediction:
        if home_team_id == away_team_id:
            raise ValueError("home_team_id and away_team_id must be different")
        home = self.lineups.predict(team_id=home_team_id, as_of=as_of)
        away = self.lineups.predict(team_id=away_team_id, as_of=as_of)
        spatial = self.spatial_matchups.predict(home_lineup=home, away_lineup=away)
        if spatial is not None:
            return spatial
        fallback = self.matchups.predict(home_lineup=home, away_lineup=away)
        return fallback.model_copy(
            update={
                "warnings": (*fallback.warnings, "Spatial event coverage was insufficient; used positional attributes."),
            }
        )
