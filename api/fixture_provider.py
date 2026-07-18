"""Fixture/live provider boundary with a terms-safe canonical implementation."""

from datetime import datetime, time, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from api.schemas import FixtureCandidate, LiveResponse
from database.models import Match, Team


class CanonicalFixtureProvider:
    """Search fixtures already licensed/normalized into the local database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, *, limit: int = 20) -> list[FixtureCandidate]:
        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(Match, home, away)
            .join(home, Match.home_team == home.id)
            .join(away, Match.away_team == away.id)
            .where(Match.date >= datetime.now(timezone.utc).date())
            .order_by(Match.date, Match.id)
            .limit(limit)
        )
        if query.strip():
            term = f"%{query.strip()}%"
            statement = statement.where(or_(home.name.ilike(term), away.name.ilike(term)))
        return [
            FixtureCandidate(
                provider="canonical",
                external_id=str(match.id),
                home_name=home_team.name,
                away_name=away_team.name,
                kickoff_at=datetime.combine(match.date, time(12), tzinfo=timezone.utc),
                match_id=match.id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                timing_accuracy="date_only",
            )
            for match, home_team, away_team in self.session.execute(statement).all()
        ]


class LiveFixtureProvider:
    """Replaceable live-data boundary; no unlicensed FotMob automation."""

    def confirmed_lineups(self, external_id: str) -> tuple[list[dict], list[dict]] | None:
        return None

    def live(self, external_id: str, *, scheduled_status: str) -> LiveResponse:
        return LiveResponse(status=scheduled_status, events=[])
