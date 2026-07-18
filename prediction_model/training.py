"""Train and persist the chronological LightGBM goal-rate baseline."""

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance
from sqlalchemy.orm import Session

from prediction_model.contracts import TrainingReport, ValidationMetrics
from prediction_model.dataset import MatchTrainingDatasetBuilder, TrainingMatrix

MODEL_VERSION = "lightgbm_poisson_v1"
DEFAULT_ARTIFACT_DIRECTORY = Path("artifacts/models/lightgbm_poisson_v1")


class LightGBMBaselineTrainer:
    """Evaluate chronologically, then retrain goal models on all available rows."""

    def __init__(
        self,
        session: Session,
        *,
        artifact_directory: str | Path = DEFAULT_ARTIFACT_DIRECTORY,
        validation_fraction: float = 0.2,
        random_seed: int = 20260719,
    ) -> None:
        if not 0.1 <= validation_fraction <= 0.4:
            raise ValueError("validation_fraction must be between 0.1 and 0.4")
        self.session = session
        self.artifact_directory = Path(artifact_directory)
        self.validation_fraction = validation_fraction
        self.random_seed = random_seed

    def train(self) -> TrainingReport:
        matrix = MatchTrainingDatasetBuilder(self.session).build()
        split = max(1, min(len(matrix.dates) - 1, round(len(matrix.dates) * (1 - self.validation_fraction))))
        train_x, validation_x = matrix.features[:split], matrix.features[split:]
        metrics: dict[str, float] = {}
        best_iterations: dict[str, int] = {}
        final_models: dict[str, lgb.Booster] = {}
        for label, targets in (("home_goals", matrix.home_goals), ("away_goals", matrix.away_goals)):
            evaluation_model = self._fit(
                train_x,
                targets[:split],
                matrix.feature_names,
                validation_x=validation_x,
                validation_y=targets[split:],
            )
            predictions = np.clip(evaluation_model.predict(validation_x), 0.05, 8.0)
            metrics[f"{label}_mae"] = float(mean_absolute_error(targets[split:], predictions))
            metrics[f"{label}_poisson"] = float(mean_poisson_deviance(targets[split:], predictions))
            iteration = evaluation_model.best_iteration or evaluation_model.current_iteration()
            best_iterations[label] = int(iteration)
            final_models[label] = self._fit(
                matrix.features,
                targets,
                matrix.feature_names,
                num_boost_round=max(1, int(iteration)),
            )
        self.artifact_directory.mkdir(parents=True, exist_ok=True)
        final_models["home_goals"].save_model(str(self.artifact_directory / "home_goals.txt"))
        final_models["away_goals"].save_model(str(self.artifact_directory / "away_goals.txt"))
        validation = ValidationMetrics(
            rows=len(matrix.dates) - split,
            start_date=matrix.dates[split],
            end_date=matrix.dates[-1],
            home_goal_mae=metrics["home_goals_mae"],
            away_goal_mae=metrics["away_goals_mae"],
            combined_goal_mae=(metrics["home_goals_mae"] + metrics["away_goals_mae"]) / 2,
            home_poisson_deviance=metrics["home_goals_poisson"],
            away_poisson_deviance=metrics["away_goals_poisson"],
        )
        report = TrainingReport(
            model_version=MODEL_VERSION,
            artifact_directory=str(self.artifact_directory.resolve()),
            dataset_rows=len(matrix.dates),
            training_rows=split,
            validation=validation,
            feature_count=len(matrix.feature_names),
            feature_names=matrix.feature_names,
            best_iterations=best_iterations,
            trained_through=matrix.dates[-1],
            limitations=(
                "Training data is limited to open World Cup match results.",
                "Older open-data editions contain selected matches rather than complete tournaments.",
                "Scores may include extra time; regulation and extra-time labels are not yet separated.",
                "Historical matchup and lineup coverage is not yet dense enough for baseline training features.",
            ),
        )
        metadata = report.model_dump(mode="json")
        metadata["feature_importance_gain"] = self._importance(final_models, matrix.feature_names)
        (self.artifact_directory / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        return report

    def _fit(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        feature_names: tuple[str, ...],
        *,
        validation_x: np.ndarray | None = None,
        validation_y: np.ndarray | None = None,
        num_boost_round: int = 300,
    ) -> lgb.Booster:
        params = {
            "objective": "poisson",
            "metric": ("poisson", "l1"),
            "learning_rate": 0.04,
            "num_leaves": 15,
            "min_data_in_leaf": 8,
            "feature_fraction": 0.85,
            "bagging_fraction": 0.9,
            "bagging_freq": 1,
            "lambda_l1": 0.1,
            "lambda_l2": 0.5,
            "seed": self.random_seed,
            "feature_fraction_seed": self.random_seed,
            "bagging_seed": self.random_seed,
            "verbosity": -1,
            "num_threads": 1,
        }
        training = lgb.Dataset(features, label=targets, feature_name=list(feature_names))
        valid_sets = None
        callbacks: list = [lgb.log_evaluation(period=0)]
        if validation_x is not None and validation_y is not None:
            valid_sets = [lgb.Dataset(validation_x, label=validation_y, reference=training)]
            callbacks.append(lgb.early_stopping(30, verbose=False))
        return lgb.train(
            params,
            training,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            callbacks=callbacks,
        )

    @staticmethod
    def _importance(models: dict[str, lgb.Booster], names: tuple[str, ...]) -> dict[str, dict[str, float]]:
        return {
            label: {
                name: float(value)
                for name, value in sorted(
                    zip(names, model.feature_importance(importance_type="gain")),
                    key=lambda item: item[1],
                    reverse=True,
                )
            }
            for label, model in models.items()
        }
