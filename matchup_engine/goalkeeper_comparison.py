"""Evidence-led comparison for goalkeepers, who are not spatial opponents."""

from dataclasses import dataclass
from datetime import date
from math import tanh

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from database.models import Lineup, Match, PlayerMatchStat
from matchup_engine.contracts import BattlePrediction, PredictedLineup


@dataclass(frozen=True, slots=True)
class GoalkeeperProfile:
    starts: int
    minutes: int
    goals_conceded_per_90: float | None
    clean_sheet_rate: float | None
    xg_prevented_per_90: float | None
    average_rating: float | None

    def public_metrics(self) -> dict[str, float | int | None]:
        return {
            "starts": self.starts,
            "minutes": self.minutes,
            "goals_conceded_per_90": self.goals_conceded_per_90,
            "clean_sheet_rate": self.clean_sheet_rate,
            "xg_prevented_per_90": self.xg_prevented_per_90,
            "average_rating": self.average_rating,
        }


class GoalkeeperComparisonEngine:
    """Compare shot prevention and outcomes instead of pitch-space overlap."""

    def __init__(self, session: Session, *, lookback_matches: int = 20) -> None:
        self.session = session
        self.lookback_matches = lookback_matches

    def predict(
        self, *, home_lineup: PredictedLineup, away_lineup: PredictedLineup
    ) -> BattlePrediction | None:
        home = next((player for player in home_lineup.players if player.assigned_role == "GK"), None)
        away = next((player for player in away_lineup.players if player.assigned_role == "GK"), None)
        if home is None or away is None:
            return None
        home_profile = self._profile(home.player_id, home_lineup.team_id, home_lineup.as_of)
        away_profile = self._profile(away.player_id, away_lineup.team_id, away_lineup.as_of)
        advantage, dimensions = self._score(home_profile, away_profile)
        confidence = min(1.0, min(home_profile.starts, away_profile.starts) / 8) * (len(dimensions) / 4)
        explanation = (
            "Goalkeepers are compared on recent goal prevention, clean sheets, goals conceded "
            "and match ratings—not player-to-player heatmap overlap."
            if dimensions else
            "No comparable goalkeeper history is loaded yet; the model leaves this edge "
            "unscored rather than inventing a 50/50 duel."
        )
        return BattlePrediction(
            label=f"Goal prevention: {home.player_name} vs {away.player_name}",
            home_role="GK",
            away_role="GK",
            home_player=home,
            away_player=away,
            home_advantage=advantage,
            confidence=confidence,
            weight=0.75,
            evidence_dimensions=tuple(dimensions),
            missing_dimensions=tuple(
                name for name in (
                    "goals_conceded_per_90", "clean_sheet_rate",
                    "xg_prevented_per_90", "average_rating",
                ) if name not in dimensions
            ),
            explanation=explanation,
            method="goalkeeper_form_comparison",
            goalkeeper_evidence={
                "home": home_profile.public_metrics(),
                "away": away_profile.public_metrics(),
            },
        )

    def _profile(self, player_id: int, team_id: int, as_of: date) -> GoalkeeperProfile:
        rows = self.session.execute(
            select(Match, Lineup, PlayerMatchStat)
            .join(Lineup, Lineup.match_id == Match.id)
            .outerjoin(
                PlayerMatchStat,
                and_(PlayerMatchStat.match_id == Match.id, PlayerMatchStat.player_id == player_id),
            )
            .where(
                Lineup.player_id == player_id,
                Lineup.team_id == team_id,
                Lineup.starter.is_(True),
                Match.date < as_of,
            )
            .order_by(Match.date.desc())
            .limit(self.lookback_matches)
        ).all()
        minutes = goals_conceded = clean_sheets = scored_matches = 0
        xg_faced = 0.0
        xg_goals_conceded = 0
        xg_minutes = 0
        xg_matches = 0
        ratings: list[float] = []
        for match, lineup, stats in rows:
            played = lineup.minutes_played or (stats.minutes if stats else None) or 90
            minutes += played
            is_home = match.home_team == team_id
            conceded = match.away_goals if is_home else match.home_goals
            if conceded is not None:
                goals_conceded += conceded
                clean_sheets += int(conceded == 0)
                scored_matches += 1
            faced = match.away_xg if is_home else match.home_xg
            if faced is not None and conceded is not None:
                xg_faced += faced
                xg_goals_conceded += conceded
                xg_minutes += played
                xg_matches += 1
            if stats and stats.rating is not None:
                ratings.append(stats.rating)
        starts = len(rows)
        per_90 = 90 / minutes if minutes else None
        return GoalkeeperProfile(
            starts=starts,
            minutes=minutes,
            goals_conceded_per_90=goals_conceded * per_90 if per_90 is not None else None,
            clean_sheet_rate=clean_sheets / scored_matches if scored_matches else None,
            xg_prevented_per_90=(xg_faced - xg_goals_conceded) * (90 / xg_minutes) if xg_minutes else None,
            average_rating=sum(ratings) / len(ratings) if ratings else None,
        )

    @staticmethod
    def _score(home: GoalkeeperProfile, away: GoalkeeperProfile) -> tuple[float | None, list[str]]:
        components: list[float] = []
        dimensions: list[str] = []
        for name, home_value, away_value, scale in (
            ("goals_conceded_per_90", home.goals_conceded_per_90, away.goals_conceded_per_90, -1.0),
            ("clean_sheet_rate", home.clean_sheet_rate, away.clean_sheet_rate, 2.0),
            ("xg_prevented_per_90", home.xg_prevented_per_90, away.xg_prevented_per_90, 1.0),
            ("average_rating", home.average_rating, away.average_rating, 0.5),
        ):
            if home_value is None or away_value is None:
                continue
            components.append(tanh((home_value - away_value) * scale))
            dimensions.append(name)
        return (sum(components) / len(components), dimensions) if components else (None, dimensions)
