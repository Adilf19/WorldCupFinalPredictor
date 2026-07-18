"""Provider-neutral, validated records exchanged by collection adapters."""

from datetime import date
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderRecord(BaseModel):
    """Strict immutable base for every provider record."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CompetitionRecord(ProviderRecord):
    """A competition in a provider's namespace."""

    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    competition_type: str | None = Field(default=None, max_length=50)
    competition_tier: float | None = Field(default=None, ge=0.0, le=1.0)


class TeamRecord(ProviderRecord):
    """A club or national team in a provider's namespace."""

    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    fifa_ranking: int | None = Field(default=None, ge=1)
    elo_rating: float | None = Field(default=None, ge=0)
    manager: str | None = Field(default=None, max_length=100)
    playing_style: str | None = Field(default=None, max_length=50)


class PlayerRecord(ProviderRecord):
    """A player identity and provider-supplied stable attributes."""

    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    nationality: str | None = Field(default=None, max_length=100)
    primary_position: str | None = Field(default=None, max_length=20)
    secondary_position: str | None = Field(default=None, max_length=20)
    preferred_foot: str | None = Field(default=None, max_length=10)
    height_cm: int | None = Field(default=None, ge=100, le=250)
    date_of_birth: date | None = None
    pace: float | None = Field(default=None, ge=0)
    strength: float | None = Field(default=None, ge=0)
    passing: float | None = Field(default=None, ge=0)
    dribbling: float | None = Field(default=None, ge=0)
    finishing: float | None = Field(default=None, ge=0)
    defending: float | None = Field(default=None, ge=0)
    creativity: float | None = Field(default=None, ge=0)


class MatchRecord(ProviderRecord):
    """A match referencing other records by provider external ID."""

    external_id: str = Field(min_length=1, max_length=255)
    competition_external_id: str = Field(min_length=1, max_length=255)
    home_team_external_id: str = Field(min_length=1, max_length=255)
    away_team_external_id: str = Field(min_length=1, max_length=255)
    date: date
    home_goals: int | None = Field(default=None, ge=0)
    away_goals: int | None = Field(default=None, ge=0)
    home_xg: float | None = Field(default=None, ge=0)
    away_xg: float | None = Field(default=None, ge=0)
    home_possession: float | None = Field(default=None, ge=0, le=100)
    away_possession: float | None = Field(default=None, ge=0, le=100)
    home_shots: int | None = Field(default=None, ge=0)
    away_shots: int | None = Field(default=None, ge=0)
    home_pass_accuracy: float | None = Field(default=None, ge=0, le=100)
    away_pass_accuracy: float | None = Field(default=None, ge=0, le=100)
    venue: str | None = Field(default=None, max_length=50)


class LineupRecord(ProviderRecord):
    """A player's role in a provider match."""

    match_external_id: str = Field(min_length=1, max_length=255)
    player_external_id: str = Field(min_length=1, max_length=255)
    team_external_id: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=20)
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    starter: bool | None = None
    minutes_played: int | None = Field(default=None, ge=0, le=130)


class PlayerMatchStatsRecord(ProviderRecord):
    """One player's aggregate statistics in a provider match."""

    match_external_id: str = Field(min_length=1, max_length=255)
    player_external_id: str = Field(min_length=1, max_length=255)
    minutes: int | None = Field(default=None, ge=0, le=130)
    goals: int | None = Field(default=None, ge=0)
    assists: int | None = Field(default=None, ge=0)
    xg: float | None = Field(default=None, ge=0)
    xa: float | None = Field(default=None, ge=0)
    shots: int | None = Field(default=None, ge=0)
    shots_on_target: int | None = Field(default=None, ge=0)
    key_passes: int | None = Field(default=None, ge=0)
    progressive_passes: int | None = Field(default=None, ge=0)
    progressive_carries: int | None = Field(default=None, ge=0)
    successful_dribbles: int | None = Field(default=None, ge=0)
    tackles: int | None = Field(default=None, ge=0)
    interceptions: int | None = Field(default=None, ge=0)
    clearances: int | None = Field(default=None, ge=0)
    duels_won: int | None = Field(default=None, ge=0)
    duels_lost: int | None = Field(default=None, ge=0)
    fouls_won: int | None = Field(default=None, ge=0)
    fouls_committed: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=10)


class MatchupEventRecord(ProviderRecord):
    """Aggregated player-v-player output in a provider match."""

    match_external_id: str = Field(min_length=1, max_length=255)
    attacker_external_id: str = Field(min_length=1, max_length=255)
    defender_external_id: str = Field(min_length=1, max_length=255)
    attacker_position: str | None = Field(default=None, max_length=20)
    defender_position: str | None = Field(default=None, max_length=20)
    minutes_together: int | None = Field(default=None, ge=0, le=130)
    dribble_attempts: int | None = Field(default=None, ge=0)
    dribbles_completed: int | None = Field(default=None, ge=0)
    attacking_duels_won: int | None = Field(default=None, ge=0)
    attacking_duels_lost: int | None = Field(default=None, ge=0)
    defensive_duels_won: int | None = Field(default=None, ge=0)
    defensive_duels_lost: int | None = Field(default=None, ge=0)
    chances_created: float | None = Field(default=None, ge=0)
    xg_generated: float | None = Field(default=None, ge=0)
    xa_generated: float | None = Field(default=None, ge=0)


class ProviderSnapshot(ProviderRecord):
    """One internally consistent provider payload ready for normalization."""

    competitions: tuple[CompetitionRecord, ...] = ()
    teams: tuple[TeamRecord, ...] = ()
    players: tuple[PlayerRecord, ...] = ()
    matches: tuple[MatchRecord, ...] = ()
    lineups: tuple[LineupRecord, ...] = ()
    player_match_stats: tuple[PlayerMatchStatsRecord, ...] = ()
    matchup_events: tuple[MatchupEventRecord, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> "ProviderSnapshot":
        """Reject duplicate IDs while allowing incremental provider snapshots."""
        self._unique_ids("competitions", self.competitions)
        self._unique_ids("teams", self.teams)
        self._unique_ids("players", self.players)
        self._unique_ids("matches", self.matches)
        return self

    @staticmethod
    def _unique_ids(label: str, records: tuple[ProviderRecord, ...]) -> set[str]:
        ids = [str(getattr(record, "external_id")) for record in records]
        duplicates = {value for value, count in Counter(ids).items() if count > 1}
        if duplicates:
            raise ValueError(f"Duplicate {label} external IDs: {sorted(duplicates)}")
        return set(ids)
