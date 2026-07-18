"""Validated JSON-file provider for fixtures, exports, and integration testing."""

import asyncio
import json
from pathlib import Path
from typing import Any

from data_collection.contracts import (
    CompetitionRecord,
    LineupRecord,
    MatchRecord,
    MatchupEventRecord,
    PlayerMatchStatsRecord,
    PlayerAvailabilityRecord,
    PlayerRecord,
    ProviderSnapshot,
    SpatialEventRecord,
    TeamRecord,
)
from data_collection.providers.base import DataProvider, validate_provider_key


class JsonFileProvider(DataProvider):
    """Load a complete provider-neutral snapshot from a local JSON document."""

    def __init__(self, path: str | Path, *, provider_key: str) -> None:
        self.path = Path(path)
        self._key = validate_provider_key(provider_key)
        self._snapshot: ProviderSnapshot | None = None

    @property
    def key(self) -> str:
        return self._key

    async def fetch_competitions(self) -> tuple[CompetitionRecord, ...]:
        return (await self._load()).competitions

    async def fetch_teams(self) -> tuple[TeamRecord, ...]:
        return (await self._load()).teams

    async def fetch_players(self) -> tuple[PlayerRecord, ...]:
        return (await self._load()).players

    async def fetch_matches(self) -> tuple[MatchRecord, ...]:
        return (await self._load()).matches

    async def fetch_player_availability(self) -> tuple[PlayerAvailabilityRecord, ...]:
        return (await self._load()).player_availability

    async def fetch_lineups(self) -> tuple[LineupRecord, ...]:
        return (await self._load()).lineups

    async def fetch_player_match_stats(self) -> tuple[PlayerMatchStatsRecord, ...]:
        return (await self._load()).player_match_stats

    async def fetch_matchup_events(self) -> tuple[MatchupEventRecord, ...]:
        return (await self._load()).matchup_events

    async def fetch_spatial_events(self) -> tuple[SpatialEventRecord, ...]:
        return (await self._load()).spatial_events

    async def fetch_snapshot(self) -> ProviderSnapshot:
        """Return the validated file snapshot without reassembling it."""
        return await self._load()

    async def _load(self) -> ProviderSnapshot:
        if self._snapshot is None:
            payload = await asyncio.to_thread(self._read_json)
            self._snapshot = ProviderSnapshot.model_validate(payload)
        return self._snapshot

    def _read_json(self) -> Any:
        with self.path.open(encoding="utf-8") as source:
            return json.load(source)
