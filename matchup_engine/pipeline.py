"""Combined lineup and positional-matchup prediction pipeline."""

from datetime import date

from sqlalchemy.orm import Session

from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupPrediction
from matchup_engine.goalkeeper_comparison import GoalkeeperComparisonEngine
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
        self.goalkeepers = GoalkeeperComparisonEngine(session)

    def predict(
        self, *, home_team_id: int, away_team_id: int, as_of: date
    ) -> MatchupPrediction:
        if home_team_id == away_team_id:
            raise ValueError("home_team_id and away_team_id must be different")
        home = self.lineups.predict(team_id=home_team_id, as_of=as_of)
        away = self.lineups.predict(team_id=away_team_id, as_of=as_of)
        prediction = self.spatial_matchups.predict(home_lineup=home, away_lineup=away)
        if prediction is None:
            fallback = self.matchups.predict(home_lineup=home, away_lineup=away)
            prediction = fallback.model_copy(update={
                "warnings": (*fallback.warnings, "Spatial event coverage was insufficient; used positional attributes."),
            })
        keeper = self.goalkeepers.predict(home_lineup=home, away_lineup=away)
        outfield = tuple(
            battle for battle in prediction.battles
            if battle.home_role != "GK" and battle.away_role != "GK"
        )
        battles = ((keeper,) if keeper is not None else ()) + outfield
        denominator = sum(battle.weight * battle.confidence for battle in battles)
        overall = (
            sum(
                float(battle.home_advantage or 0) * battle.weight * battle.confidence
                for battle in battles
            ) / denominator
            if denominator else None
        )
        biggest = max(
            (battle for battle in battles if battle.home_advantage is not None),
            key=lambda battle: abs(float(battle.home_advantage)),
            default=None,
        )
        return prediction.model_copy(update={
            "battles": battles,
            "overall_home_advantage": overall,
            "biggest_differentiator": biggest.label if biggest else None,
        })
