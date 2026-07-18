"""CC0 international-results adapter for recent national-team form."""

import asyncio
import csv
import io
import re
from datetime import date, timedelta
from urllib.request import Request, urlopen

from data_collection.contracts import CompetitionRecord, MatchRecord, PlayerRecord, ProviderSnapshot, TeamRecord
from data_collection.providers.base import DataProvider

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


class InternationalResultsProvider(DataProvider):
    """Load recent full internationals involving selected countries."""

    def __init__(self, *, team_names: tuple[str, ...] = ("Spain", "Argentina"), as_of: date | None = None, lookback_days: int = 730) -> None:
        self.team_names = frozenset(team_names)
        self.as_of = as_of or date.today()
        self.lookback_days = lookback_days
        self._snapshot: ProviderSnapshot | None = None

    @property
    def key(self) -> str:
        return "international_results"

    async def fetch_snapshot(self) -> ProviderSnapshot:
        if self._snapshot is not None:
            return self._snapshot

        def read_rows() -> list[dict[str, str]]:
            request = Request(RESULTS_URL, headers={"User-Agent": "WorldCupFinalPredictor/1.0"})
            with urlopen(request, timeout=60) as response:
                return list(csv.DictReader(io.StringIO(response.read().decode("utf-8"))))

        rows = await asyncio.to_thread(read_rows)
        since = self.as_of - timedelta(days=self.lookback_days)
        selected = [
            row for row in rows
            if since <= date.fromisoformat(row["date"]) < self.as_of
            and {row["home_team"], row["away_team"]} & self.team_names
            and row["home_score"].isdigit()
            and row["away_score"].isdigit()
        ]
        competitions: dict[str, CompetitionRecord] = {}
        teams: dict[str, TeamRecord] = {}
        matches: list[MatchRecord] = []
        for row in selected:
            competition_id = _key(row["tournament"])
            competitions[competition_id] = CompetitionRecord(
                external_id=competition_id,
                name=row["tournament"],
                country="International",
                competition_type="international",
                format="hybrid",
                team_type="country",
                competition_tier=0.75 if row["tournament"] != "Friendly" else 0.5,
            )
            for name in (row["home_team"], row["away_team"]):
                teams[_key(name)] = TeamRecord(
                    external_id=_key(name), name=name, country=name, team_type="country"
                )
            match_date = date.fromisoformat(row["date"])
            matches.append(MatchRecord(
                external_id=f"{match_date}:{_key(row['home_team'])}:{_key(row['away_team'])}:{competition_id}",
                competition_external_id=competition_id,
                home_team_external_id=_key(row["home_team"]),
                away_team_external_id=_key(row["away_team"]),
                date=match_date,
                home_goals=int(row["home_score"]),
                away_goals=int(row["away_score"]),
                venue=", ".join(value for value in (row.get("city"), row.get("country")) if value)[:50] or None,
            ))
        self._snapshot = ProviderSnapshot(
            competitions=tuple(competitions.values()), teams=tuple(teams.values()), matches=tuple(matches)
        )
        return self._snapshot

    async def fetch_competitions(self): return (await self.fetch_snapshot()).competitions
    async def fetch_teams(self): return (await self.fetch_snapshot()).teams
    async def fetch_players(self) -> tuple[PlayerRecord, ...]: return ()
    async def fetch_matches(self): return (await self.fetch_snapshot()).matches
    async def fetch_lineups(self): return ()
    async def fetch_player_match_stats(self): return ()
    async def fetch_matchup_events(self): return ()
