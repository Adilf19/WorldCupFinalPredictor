"""Fixture/live provider boundary with a terms-safe canonical implementation."""

from datetime import datetime, time, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from api.schemas import CompetitionCandidate, FixtureCandidate, LiveResponse
from api.config import ApiSettings, settings
from data_collection.api_football import ApiFootballClient, ApiFootballLiveProvider
from data_collection.providers.football_data import (
    FootballDataClient,
    KNOCKOUT_STAGES,
    competition_context,
)
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


class FootballDataFixtureProvider:
    """Upcoming fixtures from the authenticated football-data.org API."""

    def __init__(self, config: ApiSettings = settings) -> None:
        if not config.football_data_api_token:
            raise ValueError("FOOTBALL_DATA_API_TOKEN is not configured")
        self.client = FootballDataClient(
            token=config.football_data_api_token,
            base_url=config.football_data_base_url,
        )

    async def competitions(self) -> list[CompetitionCandidate]:
        results = []
        for raw in await self.client.competitions():
            format_name, team_type = competition_context(raw)
            season = raw.get("currentSeason") or {}
            start = season.get("startDate")
            results.append(CompetitionCandidate(
                provider="football_data",
                external_id=str(raw["id"]),
                code=raw.get("code"),
                name=raw["name"],
                country=(raw.get("area") or {}).get("name"),
                format=format_name,
                team_type=team_type,
                current_season=int(start[:4]) if start else None,
            ))
        return sorted(results, key=lambda item: (item.country or "", item.name))

    async def search(self, competition: str, query: str = "", *, limit: int = 50) -> list[FixtureCandidate]:
        raw_matches = await self.client.matches(competition)
        now = datetime.now(timezone.utc)
        results = []
        for raw in raw_matches:
            kickoff = datetime.fromisoformat(raw["utcDate"].replace("Z", "+00:00"))
            if kickoff < now or raw.get("status") in {"FINISHED", "CANCELLED"}:
                continue
            home, away = raw["homeTeam"], raw["awayTeam"]
            if query.strip() and query.casefold() not in f"{home['name']} {away['name']}".casefold():
                continue
            competition_raw = raw["competition"]
            base_format, _ = competition_context(competition_raw)
            stage = raw.get("stage")
            results.append(FixtureCandidate(
                provider="football_data",
                external_id=str(raw["id"]),
                home_name=home["name"],
                away_name=away["name"],
                kickoff_at=kickoff,
                timing_accuracy="exact",
                competition_name=competition_raw["name"],
                competition_format="knockout" if stage in KNOCKOUT_STAGES else ("league" if base_format == "league" else "league"),
            ))
        return sorted(results, key=lambda item: item.kickoff_at)[:limit]


class LiveFixtureProvider:
    """Live-data boundary backed by API-Football for its selected fixtures."""

    def __init__(self, config: ApiSettings = settings) -> None:
        self.api_football = (
            ApiFootballLiveProvider(ApiFootballClient(
                api_key=config.api_football_api_key,
                base_url=config.api_football_base_url,
            ))
            if config.api_football_api_key else None
        )

    def confirmed_lineups(
        self, provider: str, external_id: str
    ) -> tuple[list[dict], list[dict]] | None:
        if provider == "api_football" and self.api_football is not None:
            return self.api_football.confirmed_lineups(external_id)
        return None

    def live(self, provider: str, external_id: str, *, scheduled_status: str) -> LiveResponse:
        if provider == "api_football" and self.api_football is not None:
            return LiveResponse.model_validate(
                self.api_football.live(external_id, scheduled_status=scheduled_status)
            )
        return LiveResponse(status=scheduled_status, events=[])
