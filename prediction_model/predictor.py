"""Load the persisted LightGBM baseline and predict match goal rates."""

import json
from datetime import date
from pathlib import Path

import lightgbm as lgb
from sqlalchemy.orm import Session

from prediction_model.contracts import GoalRatePrediction
from prediction_model.dataset import MatchTrainingDatasetBuilder
from prediction_model.training import DEFAULT_ARTIFACT_DIRECTORY


class LightGBMGoalPredictor:
    def __init__(
        self,
        session: Session,
        *,
        artifact_directory: str | Path = DEFAULT_ARTIFACT_DIRECTORY,
    ) -> None:
        directory = Path(artifact_directory)
        metadata_path = directory / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Model metadata was not found at {metadata_path}")
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.feature_names = tuple(self.metadata["feature_names"])
        self.home_model = lgb.Booster(model_file=str(directory / "home_goals.txt"))
        self.away_model = lgb.Booster(model_file=str(directory / "away_goals.txt"))
        self.dataset = MatchTrainingDatasetBuilder(session)

    def predict(
        self, *, home_team_id: int, away_team_id: int, as_of: date
    ) -> GoalRatePrediction:
        row, coverage = self.dataset.inference_row(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            as_of=as_of,
            feature_names=self.feature_names,
        )
        home = min(8.0, max(0.05, float(self.home_model.predict(row)[0])))
        away = min(8.0, max(0.05, float(self.away_model.predict(row)[0])))
        return GoalRatePrediction(
            model_version=self.metadata["model_version"],
            as_of=as_of,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            expected_goals_home=home,
            expected_goals_away=away,
            feature_coverage=coverage,
        )
