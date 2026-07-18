"""Read-only match-history queries used by feature pipelines."""

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from database.models import Match


class TeamMatchHistory:
    """Retrieve leakage-safe completed matches for one team."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def completed_before(
        self, *, team_id: int, as_of: date, limit: int, lookback_days: int | None = None
    ) -> list[Match]:
        """Return newest completed matches strictly before the cutoff date."""
        statement = (
            select(Match)
            .where(
                or_(Match.home_team == team_id, Match.away_team == team_id),
                Match.date < as_of,
                Match.date >= as_of - timedelta(days=lookback_days) if lookback_days else True,
                Match.home_goals.is_not(None),
                Match.away_goals.is_not(None),
            )
            .options(joinedload(Match.competition))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())
