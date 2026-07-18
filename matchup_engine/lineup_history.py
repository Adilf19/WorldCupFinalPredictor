"""Read-only squad and historical lineup queries."""

from datetime import date, datetime, time, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from database.models import Lineup, Match, Player, PlayerAvailability, TeamPlayer


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

    def latest_availability(
        self, *, team_id: int, player_ids: list[int], as_of: date
    ) -> dict[int, PlayerAvailability]:
        """Return the latest leakage-safe report per player before match day ends."""
        if not player_ids:
            return {}
        cutoff = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
        reports = self.session.scalars(
            select(PlayerAvailability)
            .where(
                PlayerAvailability.team_id == team_id,
                PlayerAvailability.player_id.in_(player_ids),
                PlayerAvailability.reported_at <= cutoff,
            )
            .order_by(PlayerAvailability.player_id, PlayerAvailability.reported_at.desc())
        ).all()
        latest: dict[int, PlayerAvailability] = {}
        for report in reports:
            latest.setdefault(report.player_id, report)
        return latest
