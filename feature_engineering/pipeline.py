"""High-level orchestration for two-team feature comparisons."""

from datetime import date

from sqlalchemy.orm import Session

from feature_engineering.config import TeamFeatureConfig
from feature_engineering.contracts import (
    TeamFeatureComparison,
    TeamFeatureDeltas,
    TeamFeatureVector,
)
from feature_engineering.team_features import TeamFeaturePipeline


class MatchFeaturePipeline:
    """Build two team vectors and directional matchup deltas."""

    def __init__(
        self, session: Session, *, config: TeamFeatureConfig | None = None
    ) -> None:
        self.team_features = TeamFeaturePipeline(session, config=config)

    def build(
        self, *, home_team_id: int, away_team_id: int, as_of: date
    ) -> TeamFeatureComparison:
        """Build a comparison using information available before ``as_of``."""
        if home_team_id == away_team_id:
            raise ValueError("home_team_id and away_team_id must be different")
        home = self.team_features.build(team_id=home_team_id, as_of=as_of)
        away = self.team_features.build(team_id=away_team_id, as_of=as_of)
        return TeamFeatureComparison(
            as_of=as_of,
            home=home,
            away=away,
            deltas=self._deltas(home, away),
        )

    @staticmethod
    def _deltas(home: TeamFeatureVector, away: TeamFeatureVector) -> TeamFeatureDeltas:
        return TeamFeatureDeltas(
            points_per_match=MatchFeaturePipeline._difference(
                home.points_per_match, away.points_per_match
            ),
            goal_difference=MatchFeaturePipeline._difference(
                home.goal_difference, away.goal_difference
            ),
            xg_difference=MatchFeaturePipeline._difference(
                home.xg_difference, away.xg_difference
            ),
            possession=MatchFeaturePipeline._difference(
                home.possession, away.possession
            ),
            shots_for=MatchFeaturePipeline._difference(
                home.shots_for, away.shots_for
            ),
            pass_accuracy=MatchFeaturePipeline._difference(
                home.pass_accuracy, away.pass_accuracy
            ),
            elo_rating=MatchFeaturePipeline._difference(
                home.elo_rating, away.elo_rating
            ),
            fifa_rank_advantage=MatchFeaturePipeline._difference(
                MatchFeaturePipeline._float(away.fifa_ranking),
                MatchFeaturePipeline._float(home.fifa_ranking),
            ),
        )

    @staticmethod
    def _difference(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None

    @staticmethod
    def _float(value: int | None) -> float | None:
        return float(value) if value is not None else None
