"""Read-only squad and historical lineup queries."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from database.models import Lineup, Match, Player, TeamPlayer


class LineupHistory:
    """Load eligible squad members and leakage-safe lineup evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def active_squad(self, *, team_id: int, as_of: date) -> list[Player]:
        statement = (
            select(Player)
            .join(TeamPlayer, TeamPlayer.player_id == Player.id)
            .where(
                TeamPlayer.team_id == team_id,
                or_(TeamPlayer.start_date.is_(None), TeamPlayer.start_date <= as_of),
                or_(TeamPlayer.end_date.is_(None), TeamPlayer.end_date >= as_of),
            )
            .order_by(Player.id.asc())
        )
        return list(self.session.scalars(statement).unique().all())

    def recent_lineups(
        self, *, team_id: int, as_of: date, match_limit: int
    ) -> list[Lineup]:
        match_ids = list(
            self.session.scalars(
                select(Match.id)
                .where(
                    Match.date < as_of,
                    Match.lineups.any(Lineup.team_id == team_id),
                )
                .order_by(Match.date.desc(), Match.id.desc())
                .limit(match_limit)
            ).all()
        )
        if not match_ids:
            return []
        statement = (
            select(Lineup)
            .where(Lineup.team_id == team_id, Lineup.match_id.in_(match_ids))
            .options(joinedload(Lineup.player), joinedload(Lineup.match))
        )
        return list(self.session.scalars(statement).all())
