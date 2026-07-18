"""Goal prediction, Monte Carlo simulation, and optional ORM persistence."""

from datetime import date

from sqlalchemy import delete
from sqlalchemy.orm import Session

from database.crud import PredictionRepository, SimulationResultRepository
from database.models import Match, SimulationResult
from prediction_model import GoalRatePrediction, LightGBMGoalPredictor
from simulation.contracts import MonteCarloResult
from simulation.monte_carlo import MonteCarloSimulator


class PredictionSimulationPipeline:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.predictor = LightGBMGoalPredictor(session)
        self.predictions = PredictionRepository(session)
        self.scorelines = SimulationResultRepository(session)

    def run(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        as_of: date,
        simulations: int = 100_000,
        random_seed: int = 20260719,
        match_id: int | None = None,
    ) -> tuple[GoalRatePrediction, MonteCarloResult]:
        goals = self.predictor.predict(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            as_of=as_of,
        )
        result = MonteCarloSimulator(
            simulations=simulations, random_seed=random_seed
        ).simulate(
            expected_goals_home=goals.expected_goals_home,
            expected_goals_away=goals.expected_goals_away,
        )
        if match_id is not None:
            self._persist(match_id=match_id, goals=goals, result=result)
        return goals, result

    def _persist(
        self,
        *,
        match_id: int,
        goals: GoalRatePrediction,
        result: MonteCarloResult,
    ) -> None:
        match = self.session.get(Match, match_id)
        if match is None:
            raise LookupError(f"Match with id={match_id} was not found")
        if {match.home_team, match.away_team} != {goals.home_team_id, goals.away_team_id}:
            raise ValueError("Prediction teams do not match the persistence target")
        home_name = match.home_team_rel.name if match.home_team_rel else ""
        away_name = match.away_team_rel.name if match.away_team_rel else ""
        spain_probability = (
            result.home_win_probability if home_name == "Spain"
            else result.away_win_probability if away_name == "Spain" else None
        )
        argentina_probability = (
            result.home_win_probability if home_name == "Argentina"
            else result.away_win_probability if away_name == "Argentina" else None
        )
        values = {
            "match_id": match_id,
            "model_version": goals.model_version,
            "argentina_win_probability": argentina_probability,
            "spain_win_probability": spain_probability,
            "draw_probability": result.draw_probability,
            "expected_goals_home": goals.expected_goals_home,
            "expected_goals_away": goals.expected_goals_away,
        }
        prediction = self.predictions.get_by(
            match_id=match_id, model_version=goals.model_version
        )
        prediction = (
            self.predictions.create(values)
            if prediction is None
            else self.predictions.update(prediction, values)
        )
        self.session.execute(
            delete(SimulationResult).where(SimulationResult.prediction_id == prediction.id)
        )
        for scoreline in result.scorelines:
            self.scorelines.create(
                {
                    "prediction_id": prediction.id,
                    "score_home": scoreline.home_goals,
                    "score_away": scoreline.away_goals,
                    "occurrences": scoreline.occurrences,
                    "probability": scoreline.probability,
                }
            )
