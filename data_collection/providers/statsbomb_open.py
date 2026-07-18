"""StatsBomb Open Data adapter for reproducible event-location ingestion."""

import asyncio
import json
from collections import Counter
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from data_collection.contracts import (
    CompetitionRecord,
    LineupRecord,
    MatchRecord,
    MatchupEventRecord,
    PlayerMatchStatsRecord,
    PlayerRecord,
    ProviderSnapshot,
    SpatialEventRecord,
    TeamMembershipRecord,
    TeamRecord,
)
from data_collection.providers.base import DataProvider

OPEN_DATA_ROOT = "https://raw.githubusercontent.com/hudl/open-data/master/data"

_CANONICAL_NAMES = {
    "Alexis MacAllister": "Alexis Mac Allister",
    "Daniel Olmo": "Dani Olmo",
    "Enzo Fernandez": "Enzo Fernández",
    "Ferrán Torres": "Ferran Torres",
    "Gero Rulli": "Gerónimo Rulli",
    "Yeremi Pino": "Yeremy Pino",
}

_POSITION_CODES = {
    "Goalkeeper": "GK",
    "Right Back": "RB",
    "Right Wing Back": "RB",
    "Right Center Back": "RCB",
    "Center Back": "CB",
    "Left Center Back": "LCB",
    "Left Back": "LB",
    "Left Wing Back": "LB",
    "Center Defensive Midfield": "DM",
    "Right Defensive Midfield": "DM",
    "Left Defensive Midfield": "DM",
    "Right Center Midfield": "RCM",
    "Center Midfield": "CM",
    "Left Center Midfield": "LCM",
    "Right Midfield": "RW",
    "Left Midfield": "LW",
    "Right Wing": "RW",
    "Left Wing": "LW",
    "Center Attacking Midfield": "AM",
    "Right Center Forward": "ST",
    "Center Forward": "ST",
    "Left Center Forward": "ST",
    "Secondary Striker": "ST",
}


class StatsBombOpenDataProvider(DataProvider):
    """Read selected matches and player actions from StatsBomb's public JSON."""

    def __init__(
        self,
        *,
        competition_id: int = 43,
        season_id: int = 106,
        team_names: tuple[str, ...] = ("Spain", "Argentina"),
        request_concurrency: int = 4,
        include_event_data: bool = True,
    ) -> None:
        self.competition_id = competition_id
        self.season_id = season_id
        self.team_names = frozenset(team_names)
        self.request_concurrency = request_concurrency
        self.include_event_data = include_event_data
        self._snapshot: ProviderSnapshot | None = None

    @property
    def key(self) -> str:
        return "statsbomb_open"

    async def fetch_competitions(self) -> tuple[CompetitionRecord, ...]:
        return (await self.fetch_snapshot()).competitions

    async def fetch_teams(self) -> tuple[TeamRecord, ...]:
        return (await self.fetch_snapshot()).teams

    async def fetch_players(self) -> tuple[PlayerRecord, ...]:
        return (await self.fetch_snapshot()).players

    async def fetch_matches(self) -> tuple[MatchRecord, ...]:
        return (await self.fetch_snapshot()).matches

    async def fetch_lineups(self) -> tuple[LineupRecord, ...]:
        return (await self.fetch_snapshot()).lineups

    async def fetch_player_match_stats(self) -> tuple[PlayerMatchStatsRecord, ...]:
        return ()

    async def fetch_matchup_events(self) -> tuple[MatchupEventRecord, ...]:
        return ()

    async def fetch_spatial_events(self) -> tuple[SpatialEventRecord, ...]:
        return (await self.fetch_snapshot()).spatial_events

    async def fetch_snapshot(self) -> ProviderSnapshot:
        if self._snapshot is not None:
            return self._snapshot
        match_index = await self._json(
            f"matches/{self.competition_id}/{self.season_id}.json"
        )
        selected = [
            match for match in match_index
            if not self.team_names
            or {match["home_team"]["home_team_name"], match["away_team"]["away_team_name"]}
            & self.team_names
        ]
        semaphore = asyncio.Semaphore(self.request_concurrency)

        async def match_payload(match: dict[str, Any]) -> tuple[dict[str, Any], Any, Any]:
            if not self.include_event_data:
                return match, [], []
            async with semaphore:
                lineups, events = await asyncio.gather(
                    self._json(f"lineups/{match['match_id']}.json"),
                    self._json(f"events/{match['match_id']}.json"),
                )
            return match, lineups, events

        payloads = await asyncio.gather(*(match_payload(match) for match in selected))
        self._snapshot = self._build_snapshot(payloads)
        return self._snapshot

    async def _json(self, relative_path: str) -> Any:
        url = f"{OPEN_DATA_ROOT}/{relative_path}"

        def read() -> Any:
            request = Request(url, headers={"User-Agent": "WorldCupFinalPredictor/1.0"})
            with urlopen(request, timeout=60) as response:
                return json.load(response)

        return await asyncio.to_thread(read)

    def _build_snapshot(
        self, payloads: list[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]
    ) -> ProviderSnapshot:
        if not payloads:
            return ProviderSnapshot()
        first = payloads[0][0]
        competition_external_id = f"{self.competition_id}:{self.season_id}"
        competition = CompetitionRecord(
            external_id=competition_external_id,
            name=f"{first['competition']['competition_name']} {first['season']['season_name']}",
            country=first["competition"].get("country_name"),
            competition_type="international",
            format="hybrid",
            team_type="country",
            competition_tier=1.0,
        )
        teams: dict[str, TeamRecord] = {}
        players: dict[str, PlayerRecord] = {}
        memberships: dict[tuple[str, str], TeamMembershipRecord] = {}
        matches: list[MatchRecord] = []
        lineups: list[LineupRecord] = []
        spatial: list[SpatialEventRecord] = []
        snapshot_dates = [date.fromisoformat(match["match_date"]) for match, _, _ in payloads]
        membership_start = min(snapshot_dates)
        membership_end = max(snapshot_dates)

        for match, lineup_payload, event_payload in payloads:
            match_id = str(match["match_id"])
            for side in ("home", "away"):
                raw_team = match[f"{side}_team"]
                team_id = str(raw_team[f"{side}_team_id"])
                teams[team_id] = TeamRecord(
                    external_id=team_id,
                    name=raw_team[f"{side}_team_name"],
                    country=(raw_team.get("country") or {}).get("name"),
                    team_type="country",
                )
            matches.append(
                MatchRecord(
                    external_id=match_id,
                    competition_external_id=competition_external_id,
                    home_team_external_id=str(match["home_team"]["home_team_id"]),
                    away_team_external_id=str(match["away_team"]["away_team_id"]),
                    date=date.fromisoformat(match["match_date"]),
                    home_goals=match.get("home_score"),
                    away_goals=match.get("away_score"),
                    home_xg=match.get("home_team", {}).get("home_team_xg"),
                    away_xg=match.get("away_team", {}).get("away_team_xg"),
                    venue=(match.get("stadium") or {}).get("name"),
                    stage=match.get("competition_stage", {}).get("name"),
                    is_knockout=(match.get("competition_stage", {}).get("name") or "").upper()
                    not in {"", "GROUP STAGE", "REGULAR SEASON"},
                )
            )
            max_minute = max((int(event.get("minute", 0)) for event in event_payload), default=90)
            for team_lineup in lineup_payload:
                team_id = str(team_lineup["team_id"])
                for raw_player in team_lineup["lineup"]:
                    player_id = str(raw_player["player_id"])
                    positions = raw_player.get("positions") or []
                    position_counts = Counter(
                        _POSITION_CODES.get(item["position"], item["position"][:20])
                        for item in positions
                    )
                    primary = position_counts.most_common(1)[0][0] if position_counts else None
                    display_name = raw_player.get("player_nickname") or raw_player["player_name"]
                    display_name = _CANONICAL_NAMES.get(display_name, display_name)
                    players[player_id] = PlayerRecord(
                        external_id=player_id,
                        name=display_name,
                        nationality=(raw_player.get("country") or {}).get("name"),
                        primary_position=primary,
                    )
                    memberships[(team_id, player_id)] = TeamMembershipRecord(
                        team_external_id=team_id,
                        player_external_id=player_id,
                        start_date=membership_start,
                        end_date=membership_end,
                    )
                    if positions:
                        first_position = positions[0]
                        starter = first_position.get("start_reason") == "Starting XI"
                        start = self._clock_minutes(first_position.get("from"))
                        last_end = next(
                            (self._clock_minutes(item.get("to")) for item in reversed(positions) if item.get("to")),
                            float(max_minute),
                        )
                        minutes = max(0, min(130, round(last_end - start)))
                    else:
                        starter, minutes = False, 0
                    lineups.append(
                        LineupRecord(
                            match_external_id=match_id,
                            player_external_id=player_id,
                            team_external_id=team_id,
                            position=primary,
                            shirt_number=raw_player.get("jersey_number"),
                            starter=starter,
                            minutes_played=minutes,
                        )
                    )
            for event in event_payload:
                location = event.get("location")
                raw_player = event.get("player")
                raw_team = event.get("team")
                if not location or not raw_player or not raw_team:
                    continue
                end_location, outcome = self._event_details(event)
                spatial.append(
                    SpatialEventRecord(
                        external_id=str(event["id"]),
                        match_external_id=match_id,
                        team_external_id=str(raw_team["id"]),
                        player_external_id=str(raw_player["id"]),
                        event_type=event["type"]["name"],
                        period=event["period"],
                        minute=event["minute"],
                        second=float(event.get("second", 0)),
                        x=self._unit(location[0], 120),
                        y=self._unit(location[1], 80),
                        end_x=self._unit(end_location[0], 120) if end_location else None,
                        end_y=self._unit(end_location[1], 80) if end_location else None,
                        outcome=outcome,
                        under_pressure=bool(event.get("under_pressure", False)),
                    )
                )
        return ProviderSnapshot(
            competitions=(competition,),
            teams=tuple(teams.values()),
            players=tuple(players.values()),
            team_memberships=tuple(memberships.values()),
            matches=tuple(matches),
            lineups=tuple(lineups),
            spatial_events=tuple(spatial),
        )

    @staticmethod
    def _event_details(event: dict[str, Any]) -> tuple[list[float] | None, str | None]:
        for detail_name in ("pass", "carry", "shot", "goalkeeper"):
            detail = event.get(detail_name)
            if detail:
                outcome = detail.get("outcome")
                return detail.get("end_location"), outcome.get("name") if outcome else None
        outcome = event.get("duel", {}).get("outcome") or event.get("dribble", {}).get("outcome")
        return None, outcome.get("name") if outcome else None

    @staticmethod
    def _unit(value: float, maximum: float) -> float:
        return min(1.0, max(0.0, float(value) / maximum))

    @staticmethod
    def _clock_minutes(value: str | None) -> float:
        if not value:
            return 0.0
        minutes, seconds = value.split(":", 1)
        return int(minutes) + int(seconds) / 60
