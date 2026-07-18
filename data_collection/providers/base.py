"""Abstract interface implemented by every football data provider."""

from abc import ABC, abstractmethod
import re

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
    TeamMembershipRecord,
)

_PROVIDER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,49}$")


def validate_provider_key(value: str) -> str:
    """Validate and return a stable key suitable for database mappings."""
    if not _PROVIDER_KEY_PATTERN.fullmatch(value):
        raise ValueError(
            "provider key must be 2-50 lowercase letters, numbers, '_' or '-'"
        )
    return value


class DataProvider(ABC):
    """Provider adapter contract.

    Adapters translate vendor-specific payloads into provider-neutral records.
    They must not import ORM models or write to the database.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Return the stable lowercase key used for external-ID mappings."""

    @abstractmethod
    async def fetch_competitions(self) -> tuple[CompetitionRecord, ...]:
        """Fetch competitions available for this ingestion run."""

    @abstractmethod
    async def fetch_teams(self) -> tuple[TeamRecord, ...]:
        """Fetch teams available for this ingestion run."""

    @abstractmethod
    async def fetch_players(self) -> tuple[PlayerRecord, ...]:
        """Fetch players available for this ingestion run."""

    @abstractmethod
    async def fetch_matches(self) -> tuple[MatchRecord, ...]:
        """Fetch match-level records."""

    async def fetch_team_memberships(self) -> tuple[TeamMembershipRecord, ...]:
        """Fetch player memberships when squad data is available."""
        return ()

    async def fetch_player_availability(self) -> tuple[PlayerAvailabilityRecord, ...]:
        """Fetch injuries, suspensions, and availability when licensed."""
        return ()

    @abstractmethod
    async def fetch_lineups(self) -> tuple[LineupRecord, ...]:
        """Fetch lineup records."""

    @abstractmethod
    async def fetch_player_match_stats(self) -> tuple[PlayerMatchStatsRecord, ...]:
        """Fetch player-match aggregate statistics."""

    @abstractmethod
    async def fetch_matchup_events(self) -> tuple[MatchupEventRecord, ...]:
        """Fetch aggregated player-v-player matchup events."""

    async def fetch_spatial_events(self) -> tuple[SpatialEventRecord, ...]:
        """Fetch normalized event locations when the provider exposes them."""
        return ()

    async def fetch_snapshot(self) -> ProviderSnapshot:
        """Fetch one normalized snapshot in dependency order."""
        return ProviderSnapshot(
            competitions=await self.fetch_competitions(),
            teams=await self.fetch_teams(),
            players=await self.fetch_players(),
            team_memberships=await self.fetch_team_memberships(),
            player_availability=await self.fetch_player_availability(),
            matches=await self.fetch_matches(),
            lineups=await self.fetch_lineups(),
            player_match_stats=await self.fetch_player_match_stats(),
            matchup_events=await self.fetch_matchup_events(),
            spatial_events=await self.fetch_spatial_events(),
        )
