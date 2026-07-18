"""Chronological, leakage-safe match training matrix construction."""

from dataclasses import dataclass
from datetime import date
from math import nan

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Match
from feature_engineering.pipeline import MatchFeaturePipeline


@dataclass(frozen=True, slots=True)
class TrainingMatrix:
    features: np.ndarray
    home_goals: np.ndarray
    away_goals: np.ndarray
    dates: tuple[date, ...]
    match_ids: tuple[int, ...]
    feature_names: tuple[str, ...]


class MatchTrainingDatasetBuilder:
    """Build pre-kickoff feature rows for completed canonical matches."""

    def __init__(self, session: Session, *, minimum_team_history: int = 1) -> None:
        if minimum_team_history < 0:
            raise ValueError("minimum_team_history cannot be negative")
        self.session = session
        self.minimum_team_history = minimum_team_history
        self.features = MatchFeaturePipeline(session)

    def build(self) -> TrainingMatrix:
        matches = self.session.scalars(
            select(Match)
            .where(
                Match.home_goals.is_not(None),
                Match.away_goals.is_not(None),
            )
            .order_by(Match.date, Match.id)
        ).all()
        rows: list[dict[str, float | int | None]] = []
        targets_home: list[float] = []
        targets_away: list[float] = []
        dates: list[date] = []
        ids: list[int] = []
        for match in matches:
            comparison = self.features.build(
                home_team_id=int(match.home_team),
                away_team_id=int(match.away_team),
                as_of=match.date,
            )
            if min(
                comparison.home.matches_considered,
                comparison.away.matches_considered,
            ) < self.minimum_team_history:
                continue
            values = comparison.model_features()
            values.update(
                match_year=match.date.year,
                match_month=match.date.month,
            )
            rows.append(values)
            targets_home.append(float(match.home_goals))
            targets_away.append(float(match.away_goals))
            dates.append(match.date)
            ids.append(match.id)
        if not rows:
            raise RuntimeError("No completed matches had enough pre-match history")
        candidate_names = tuple(rows[0])
        usable_names = tuple(
            name
            for name in candidate_names
            if any(row[name] is not None for row in rows)
            and len({row[name] for row in rows if row[name] is not None}) > 1
        )
        matrix = np.asarray(
            [
                [float(value) if (value := row[name]) is not None else nan for name in usable_names]
                for row in rows
            ],
            dtype=float,
        )
        return TrainingMatrix(
            features=matrix,
            home_goals=np.asarray(targets_home, dtype=float),
            away_goals=np.asarray(targets_away, dtype=float),
            dates=tuple(dates),
            match_ids=tuple(ids),
            feature_names=usable_names,
        )

    def inference_row(
        self,
        *,
        home_team_id: int,
        away_team_id: int,
        as_of: date,
        feature_names: tuple[str, ...],
    ) -> tuple[np.ndarray, float]:
        comparison = self.features.build(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            as_of=as_of,
        )
        values = comparison.model_features()
        values.update(match_year=as_of.year, match_month=as_of.month)
        available = sum(values.get(name) is not None for name in feature_names)
        row = np.asarray(
            [[float(value) if (value := values.get(name)) is not None else nan for name in feature_names]],
            dtype=float,
        )
        return row, available / len(feature_names)
