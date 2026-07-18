"""Licensed football-data.org competition, fixture, and match-history adapter."""

import asyncio
from datetime import date, datetime, timezone
from typing import Any

import httpx

from data_collection.contracts import (
    CompetitionRecord,
    LineupRecord,
    MatchRecord,
    PlayerRecord,
    ProviderSnapshot,
    TeamRecord,
    TeamMembershipRecord,
)
from data_collection.providers.base import DataProvider

KNOCKOUT_STAGES = {
    "FINAL", "THIRD_PLACE", "SEMI_FINALS", "QUARTER_FINALS", "LAST_16",
    "LAST_32", "LAST_64", "ROUND_1", "ROUND_2", "ROUND_3", "ROUND_4",
    "PLAYOFFS", "PLAYOFF_ROUND_1", "PLAYOFF_ROUND_2",
}


def competition_context(raw: dict[str, Any]) -> tuple[str, str]:
    name = str(raw.get("name") or "")
    raw_type = str(raw.get("type") or "LEAGUE").upper()
    is_country = any(token in name.lower() for token in (
        "world cup", "european championship", "nations league", "qualification",
        "copa america", "africa cup", "asian cup",
    ))
    return ("hybrid" if raw_type == "CUP" else "league", "country" if is_country else "club")


class FootballDataClient:
    def __init__(self, *, token: str, base_url: str = "https://api.football-data.org/v4") -> None:
        if not token:
            raise ValueError("FOOTBALL_DATA_API_TOKEN is not configured")
        self.token = token
        self.base_url = base_url.rstrip("/")

    async def get(self, path: str, *, params: dict[str, Any] | None = None, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
        headers = {"X-Auth-Token": self.token, **(extra_headers or {})}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers=headers,
            )
        response.raise_for_status()
        return response.json()

    async def competitions(self) -> list[dict[str, Any]]:
        return list((await self.get("competitions")).get("competitions", []))

    async def matches(self, competition: str, *, season: int | None = None) -> list[dict[str, Any]]:
        params = {"season": season} if season is not None else None
        return list((await self.get(f"competitions/{competition}/matches", params=params)).get("matches", []))


class FootballDataProvider(DataProvider):
    """Normalize one competition across explicit seasons; never scrapes webpages."""

    def __init__(self, *, token: str, competition: str, seasons: tuple[int, ...], base_url: str = "https://api.football-data.org/v4") -> None:
        self.client = FootballDataClient(token=token, base_url=base_url)
        self.competition = competition
        self.seasons = seasons
        self._snapshot: ProviderSnapshot | None = None

    @property
    def key(self) -> str:
        return "football_data"

    async def fetch_snapshot(self) -> ProviderSnapshot:
        if self._snapshot is not None:
            return self._snapshot
        payloads = await asyncio.gather(
            *(self.client.get(
                f"competitions/{self.competition}/matches",
                params={"season": season},
                extra_headers={"X-Unfold-Lineups": "true"},
            ) for season in self.seasons)
        )
        team_payloads = await asyncio.gather(
            *(self.client.get(f"competitions/{self.competition}/teams", params={"season": season}) for season in self.seasons)
        )
        raw_matches = [match for payload in payloads for match in payload.get("matches", [])]
        if not raw_matches:
            self._snapshot = ProviderSnapshot()
            return self._snapshot
        raw_competition = raw_matches[0]["competition"]
        format_name, team_type = competition_context(raw_competition)
        competition_id = str(raw_competition["id"])
        competition = CompetitionRecord(
            external_id=competition_id,
            name=raw_competition["name"],
            country=(raw_competition.get("area") or {}).get("name"),
            competition_type=str(raw_competition.get("type") or "").lower() or None,
            format=format_name,
            team_type=team_type,
            competition_tier=0.85,
        )
        teams: dict[str, TeamRecord] = {}
        players: dict[str, PlayerRecord] = {}
        memberships: dict[tuple[str, str, date | None], TeamMembershipRecord] = {}
        matches: dict[str, MatchRecord] = {}
        lineups: dict[tuple[str, str], LineupRecord] = {}
        for payload in team_payloads:
            season = payload.get("season") or {}
            start_date = date.fromisoformat(season["startDate"][:10]) if season.get("startDate") else None
            end_date = date.fromisoformat(season["endDate"][:10]) if season.get("endDate") else None
            for raw_team in payload.get("teams", []):
                team_id = str(raw_team["id"])
                teams[team_id] = TeamRecord(
                    external_id=team_id,
                    name=raw_team["name"],
                    country=(raw_team.get("area") or {}).get("name"),
                    team_type=team_type,
                    manager=(raw_team.get("coach") or {}).get("name"),
                )
                for raw_player in raw_team.get("squad") or []:
                    player_id = str(raw_player["id"])
                    players[player_id] = PlayerRecord(
                        external_id=player_id,
                        name=raw_player["name"],
                        nationality=raw_player.get("nationality"),
                        photo_url=raw_player.get("photo"),
                        primary_position=(raw_player.get("position") or "")[:20] or None,
                        date_of_birth=date.fromisoformat(raw_player["dateOfBirth"][:10]) if raw_player.get("dateOfBirth") else None,
                    )
                    memberships[(team_id, player_id, start_date)] = TeamMembershipRecord(
                        team_external_id=team_id,
                        player_external_id=player_id,
                        start_date=start_date,
                        end_date=end_date,
                    )
        for raw in raw_matches:
            for side in ("homeTeam", "awayTeam"):
                team = raw[side]
                teams[str(team["id"])] = TeamRecord(
                    external_id=str(team["id"]),
                    name=team["name"],
                    country=(team.get("area") or {}).get("name"),
                    team_type=team_type,
                )
            score = raw.get("score") or {}
            full_time = score.get("fullTime") or {}
            stage = raw.get("stage")
            matches[str(raw["id"])] = MatchRecord(
                external_id=str(raw["id"]),
                competition_external_id=competition_id,
                home_team_external_id=str(raw["homeTeam"]["id"]),
                away_team_external_id=str(raw["awayTeam"]["id"]),
                date=datetime.fromisoformat(raw["utcDate"].replace("Z", "+00:00")).date(),
                home_goals=full_time.get("home"),
                away_goals=full_time.get("away"),
                venue=raw.get("venue"),
                stage=stage,
                is_knockout=stage in KNOCKOUT_STAGES,
            )
            for side in ("homeTeam", "awayTeam"):
                raw_team = raw[side]
                team_id = str(raw_team["id"])
                for starter, label in ((True, "lineup"), (False, "bench")):
                    for raw_player in raw_team.get(label) or []:
                        player_id = str(raw_player["id"])
                        players.setdefault(player_id, PlayerRecord(
                            external_id=player_id,
                            name=raw_player["name"],
                            photo_url=raw_player.get("photo"),
                            primary_position=(raw_player.get("position") or "")[:20] or None,
                        ))
                        lineups[(str(raw["id"]), player_id)] = LineupRecord(
                            match_external_id=str(raw["id"]),
                            player_external_id=player_id,
                            team_external_id=team_id,
                            position=(raw_player.get("position") or "")[:20] or None,
                            shirt_number=raw_player.get("shirtNumber"),
                            starter=starter,
                            minutes_played=90 if starter else 0,
                        )
        self._snapshot = ProviderSnapshot(
            competitions=(competition,), teams=tuple(teams.values()), players=tuple(players.values()),
            team_memberships=tuple(memberships.values()), matches=tuple(matches.values()),
            lineups=tuple(lineups.values()),
        )
        return self._snapshot

    async def fetch_competitions(self): return (await self.fetch_snapshot()).competitions
    async def fetch_teams(self): return (await self.fetch_snapshot()).teams
    async def fetch_players(self): return (await self.fetch_snapshot()).players
    async def fetch_team_memberships(self): return (await self.fetch_snapshot()).team_memberships
    async def fetch_matches(self): return (await self.fetch_snapshot()).matches
    async def fetch_lineups(self): return (await self.fetch_snapshot()).lineups
    async def fetch_player_match_stats(self): return ()
    async def fetch_matchup_events(self): return ()
