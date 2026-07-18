"""Generate weighted rolling team features from canonical match records."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from database.models import Match, Team
from feature_engineering.config import TeamFeatureConfig
from feature_engineering.contracts import TeamFeatureVector
from feature_engineering.history import TeamMatchHistory
from feature_engineering.weighting import (
    effective_sample_size,
    recency_weight,
    weighted_average,
)


@dataclass(frozen=True, slots=True)
class TeamMatchPerspective:
    """One match normalized into the selected team's point of view."""

    weight: float
    is_home: bool
    points: float
    won: float
    drawn: float
    lost: float
    goals_for: float
    goals_against: float
    xg_for: float | None
    xg_against: float | None
    possession: float | None
    shots_for: float | None
    shots_against: float | None
    pass_accuracy: float | None
    clean_sheet: float
    scored: float


class TeamFeaturePipeline:
    """Build one leakage-safe, versioned team feature vector."""

    _STATISTIC_FIELDS = (
        "xg_for",
        "xg_against",
        "possession",
        "shots_for",
        "shots_against",
        "pass_accuracy",
    )

    def __init__(
        self, session: Session, *, config: TeamFeatureConfig | None = None
    ) -> None:
        self.session = session
        self.config = config or TeamFeatureConfig()
        self.history = TeamMatchHistory(session)

    def build(self, *, team_id: int, as_of: date) -> TeamFeatureVector:
        """Build features using only completed matches before ``as_of``."""
        team = self.session.get(Team, team_id)
        if team is None:
            raise LookupError(f"Team with id={team_id} was not found")

        matches = self.history.completed_before(
            team_id=team_id,
            as_of=as_of,
            limit=self.config.lookback_matches,
            lookback_days=self.config.lookback_days,
        )
        perspectives = [
            self._perspective(match=match, team_id=team_id, as_of=as_of)
            for match in matches
        ]
        return self._aggregate(team=team, as_of=as_of, rows=perspectives)

    def _perspective(
        self, *, match: Match, team_id: int, as_of: date
    ) -> TeamMatchPerspective:
        is_home = match.home_team == team_id
        if not is_home and match.away_team != team_id:
            raise ValueError(f"Team {team_id} did not participate in match {match.id}")
        if match.home_goals is None or match.away_goals is None:
            raise ValueError(f"Match {match.id} is not completed")

        goals_for = match.home_goals if is_home else match.away_goals
        goals_against = match.away_goals if is_home else match.home_goals
        tier = (
            match.competition.competition_tier
            if match.competition and match.competition.competition_tier is not None
            else self.config.default_competition_tier
        )
        competition_weight = max(tier, self.config.minimum_competition_weight)
        weight = competition_weight * recency_weight(
            age_days=(as_of - match.date).days,
            half_life_days=self.config.recency_half_life_days,
        )

        if goals_for > goals_against:
            points, won, drawn, lost = 3.0, 1.0, 0.0, 0.0
        elif goals_for == goals_against:
            points, won, drawn, lost = 1.0, 0.0, 1.0, 0.0
        else:
            points, won, drawn, lost = 0.0, 0.0, 0.0, 1.0

        return TeamMatchPerspective(
            weight=weight,
            is_home=is_home,
            points=points,
            won=won,
            drawn=drawn,
            lost=lost,
            goals_for=float(goals_for),
            goals_against=float(goals_against),
            xg_for=match.home_xg if is_home else match.away_xg,
            xg_against=match.away_xg if is_home else match.home_xg,
            possession=match.home_possession if is_home else match.away_possession,
            shots_for=self._float(match.home_shots if is_home else match.away_shots),
            shots_against=self._float(
                match.away_shots if is_home else match.home_shots
            ),
            pass_accuracy=(
                match.home_pass_accuracy if is_home else match.away_pass_accuracy
            ),
            clean_sheet=float(goals_against == 0),
            scored=float(goals_for > 0),
        )

    def _aggregate(
        self,
        *,
        team: Team,
        as_of: date,
        rows: list[TeamMatchPerspective],
    ) -> TeamFeatureVector:
        weights = [row.weight for row in rows]
        goals_for = self._average(rows, "goals_for")
        goals_against = self._average(rows, "goals_against")
        xg_for = self._average(rows, "xg_for")
        xg_against = self._average(rows, "xg_against")
        coverage = self._statistics_coverage(rows)
        effective_matches = effective_sample_size(weights)

        return TeamFeatureVector(
            team_id=team.id,
            team_name=team.name,
            as_of=as_of,
            matches_considered=len(rows),
            effective_sample_size=effective_matches,
            total_weight=sum(weights),
            win_rate=self._bounded_average(rows, "won", maximum=1.0),
            draw_rate=self._bounded_average(rows, "drawn", maximum=1.0),
            loss_rate=self._bounded_average(rows, "lost", maximum=1.0),
            points_per_match=self._bounded_average(rows, "points", maximum=3.0),
            goals_for=goals_for,
            goals_against=goals_against,
            goal_difference=self._difference(goals_for, goals_against),
            xg_for=xg_for,
            xg_against=xg_against,
            xg_difference=self._difference(xg_for, xg_against),
            possession=self._average(rows, "possession"),
            shots_for=self._average(rows, "shots_for"),
            shots_against=self._average(rows, "shots_against"),
            pass_accuracy=self._average(rows, "pass_accuracy"),
            clean_sheet_rate=self._bounded_average(rows, "clean_sheet", maximum=1.0),
            scoring_rate=self._bounded_average(rows, "scored", maximum=1.0),
            home_match_share=weighted_average(
                (float(row.is_home), row.weight) for row in rows
            ),
            elo_rating=team.elo_rating,
            fifa_ranking=team.fifa_ranking,
            playing_style=team.playing_style,
            manager=team.manager,
            statistics_coverage=coverage,
            sample_confidence=min(
                1.0, effective_matches / self.config.full_confidence_matches
            ),
        )

    @staticmethod
    def _average(
        rows: list[TeamMatchPerspective],
        field: str,
    ) -> float | None:
        return weighted_average(
            (getattr(row, field), row.weight) for row in rows
        )

    @staticmethod
    def _bounded_average(
        rows: list[TeamMatchPerspective], field: str, *, maximum: float
    ) -> float | None:
        value = TeamFeaturePipeline._average(rows, field)
        return min(maximum, max(0.0, value)) if value is not None else None

    def _statistics_coverage(self, rows: list[TeamMatchPerspective]) -> float:
        if not rows:
            return 0.0
        available = sum(
            getattr(row, field) is not None
            for row in rows
            for field in self._STATISTIC_FIELDS
        )
        return available / (len(rows) * len(self._STATISTIC_FIELDS))

    @staticmethod
    def _difference(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None

    @staticmethod
    def _float(value: int | None) -> float | None:
        return float(value) if value is not None else None
