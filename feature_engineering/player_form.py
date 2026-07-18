"""Leakage-safe player form split into club and country contexts."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from analytics_core import recency_weight
from database.models import Lineup, Match, PlayerMatchStat, Team
from feature_engineering.weighting import weighted_average


@dataclass(frozen=True, slots=True)
class PlayerContextForm:
    club_form: float | None
    country_form: float | None
    blended_form: float | None
    club_matches: int
    country_matches: int
    coverage: float


class PlayerFormPipeline:
    """Build contextual form without treating missing provider stats as poor form."""

    def __init__(self, session: Session, *, lookback_days: int = 730, match_limit: int = 40) -> None:
        self.session = session
        self.lookback_days = lookback_days
        self.match_limit = match_limit

    def build(self, *, player_id: int, target_team_type: str, as_of: date) -> PlayerContextForm:
        rows = self.session.execute(
            select(Lineup, Match, Team, PlayerMatchStat)
            .join(Match, Lineup.match_id == Match.id)
            .join(Team, Lineup.team_id == Team.id)
            .outerjoin(
                PlayerMatchStat,
                and_(PlayerMatchStat.match_id == Match.id, PlayerMatchStat.player_id == player_id),
            )
            .where(
                Lineup.player_id == player_id,
                Match.date < as_of,
                Match.date >= as_of - timedelta(days=self.lookback_days),
                Match.home_goals.is_not(None),
                Match.away_goals.is_not(None),
            )
            .order_by(Match.date.desc())
            .limit(self.match_limit)
        ).all()
        buckets: dict[str, list[tuple[float, float]]] = {"club": [], "country": []}
        counts = {"club": 0, "country": 0}
        stat_rows = 0
        for lineup, match, team, stats in rows:
            context = "country" if team.team_type == "country" else "club"
            minutes = min(120, max(0, lineup.minutes_played or (90 if lineup.starter else 0)))
            availability = min(1.0, minutes / 90)
            if stats and stats.rating is not None:
                performance = min(1.0, max(0.0, stats.rating / 10))
                stat_rows += 1
            else:
                performance = availability
            weight = recency_weight(age_days=(as_of - match.date).days, half_life_days=180)
            buckets[context].append((0.35 * availability + 0.65 * performance, weight))
            counts[context] += 1
        club = weighted_average(buckets["club"])
        country = weighted_average(buckets["country"])
        primary, secondary = (country, club) if target_team_type == "country" else (club, country)
        if primary is not None and secondary is not None:
            primary_weight = 0.75 if target_team_type == "country" else 0.85
            blended = primary_weight * primary + (1 - primary_weight) * secondary
        else:
            blended = primary if primary is not None else secondary
        coverage = min(1.0, len(rows) / 20) * (0.7 + 0.3 * (stat_rows / len(rows) if rows else 0))
        return PlayerContextForm(club, country, blended, counts["club"], counts["country"], coverage)
