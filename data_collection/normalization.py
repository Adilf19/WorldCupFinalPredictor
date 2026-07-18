"""Normalize provider-neutral records into canonical SQLAlchemy entities."""

from typing import Any

from sqlalchemy.orm import Session

from data_collection.contracts import ProviderSnapshot
from data_collection.normalization_support import (
    AmbiguousIdentityError,
    NormalizationError,
    NormalizationReport,
    NormalizationSupport,
    UnresolvedReferenceError,
)
from database.crud import (
    CompetitionProviderReferenceRepository,
    CompetitionRepository,
    LineupRepository,
    MatchProviderReferenceRepository,
    MatchRepository,
    MatchupEventRepository,
    PlayerMatchStatRepository,
    PlayerProviderReferenceRepository,
    PlayerRepository,
    SpatialEventRepository,
    TeamProviderReferenceRepository,
    TeamRepository,
)
from database.models import Competition, Match, Player, Team

__all__ = [
    "AmbiguousIdentityError",
    "NormalizationError",
    "NormalizationReport",
    "ProviderNormalizer",
    "UnresolvedReferenceError",
]


class ProviderNormalizer(NormalizationSupport):
    """Resolve external IDs and persist one provider snapshot atomically.

    Canonical identity fields use first-write-wins semantics: later providers
    fill missing values but do not rename existing entities. Match statistics,
    lineups, player statistics, and matchup aggregates are refreshed because
    providers commonly revise them after a match.
    """

    def __init__(self, session: Session, *, provider: str) -> None:
        super().__init__(provider=provider)
        self.competitions = CompetitionRepository(session)
        self.teams = TeamRepository(session)
        self.players = PlayerRepository(session)
        self.matches = MatchRepository(session)
        self.lineups = LineupRepository(session)
        self.player_stats = PlayerMatchStatRepository(session)
        self.matchup_events = MatchupEventRepository(session)
        self.spatial_events = SpatialEventRepository(session)
        self.competition_refs = CompetitionProviderReferenceRepository(session)
        self.team_refs = TeamProviderReferenceRepository(session)
        self.player_refs = PlayerProviderReferenceRepository(session)
        self.match_refs = MatchProviderReferenceRepository(session)

    def normalize(self, snapshot: ProviderSnapshot) -> NormalizationReport:
        """Normalize a validated snapshot in referential dependency order."""
        for record in snapshot.competitions:
            self._competition(record.model_dump(exclude_none=True))
        for record in snapshot.teams:
            self._team(record.model_dump(exclude_none=True))
        for record in snapshot.players:
            self._player(record.model_dump(exclude_none=True))
        for record in snapshot.matches:
            self._match(record.model_dump(exclude_none=True))
        for record in snapshot.lineups:
            self._lineup(record.model_dump(exclude_none=True))
        for record in snapshot.player_match_stats:
            self._player_match_stats(record.model_dump(exclude_none=True))
        for record in snapshot.matchup_events:
            self._matchup_event(record.model_dump(exclude_none=True))
        for record in snapshot.spatial_events:
            self._spatial_event(record.model_dump(exclude_none=True))
        return self.report

    def _competition(self, values: dict[str, Any]) -> Competition:
        external_id = values.pop("external_id")
        entity = self._by_reference(
            self.competition_refs, self.competitions, external_id, "competition_id"
        )
        if entity is None:
            entity = self._find_unique(
                self.competitions,
                entity_name="Competition",
                name=values["name"],
                country=values.get("country"),
            )
            if entity is None:
                entity = self.competitions.create(values)
                self.report.record("competitions", "created")
            else:
                self._fill_missing("competitions", self.competitions, entity, values)
            self.competition_refs.create(
                {
                    "provider": self.provider,
                    "external_id": external_id,
                    "competition_id": entity.id,
                }
            )
        else:
            self._fill_missing("competitions", self.competitions, entity, values)
        return entity

    def _team(self, values: dict[str, Any]) -> Team:
        external_id = values.pop("external_id")
        entity = self._by_reference(
            self.team_refs, self.teams, external_id, "team_id"
        )
        if entity is None:
            entity = self._find_unique(
                self.teams,
                entity_name="Team",
                name=values["name"],
                country=values.get("country"),
            )
            if entity is None:
                entity = self.teams.create(values)
                self.report.record("teams", "created")
            else:
                self._fill_missing("teams", self.teams, entity, values)
            self.team_refs.create(
                {
                    "provider": self.provider,
                    "external_id": external_id,
                    "team_id": entity.id,
                }
            )
        else:
            self._fill_missing("teams", self.teams, entity, values)
        return entity

    def _player(self, values: dict[str, Any]) -> Player:
        external_id = values.pop("external_id")
        entity = self._by_reference(
            self.player_refs, self.players, external_id, "player_id"
        )
        if entity is None:
            identity = {"name": values["name"]}
            if values.get("date_of_birth") is not None:
                identity["date_of_birth"] = values["date_of_birth"]
            else:
                identity["nationality"] = values.get("nationality")
            entity = self._find_unique(
                self.players, entity_name="Player", **identity
            )
            if entity is None:
                entity = self.players.create(values)
                self.report.record("players", "created")
            else:
                self._fill_missing("players", self.players, entity, values)
            self.player_refs.create(
                {
                    "provider": self.provider,
                    "external_id": external_id,
                    "player_id": entity.id,
                }
            )
        else:
            self._fill_missing("players", self.players, entity, values)
        return entity

    def _match(self, values: dict[str, Any]) -> Match:
        external_id = values.pop("external_id")
        competition_id = self._required_id(
            self.competition_refs,
            values.pop("competition_external_id"),
            "competition_id",
            "competition",
        )
        home_team_id = self._required_id(
            self.team_refs,
            values.pop("home_team_external_id"),
            "team_id",
            "home team",
        )
        away_team_id = self._required_id(
            self.team_refs,
            values.pop("away_team_external_id"),
            "team_id",
            "away team",
        )
        values.update(
            competition_id=competition_id,
            home_team=home_team_id,
            away_team=away_team_id,
        )
        entity = self._by_reference(
            self.match_refs, self.matches, external_id, "match_id"
        )
        if entity is None:
            entity = self._find_unique(
                self.matches,
                entity_name="Match",
                competition_id=competition_id,
                date=values["date"],
                home_team=home_team_id,
                away_team=away_team_id,
            )
            if entity is None:
                entity = self.matches.create(values)
                self.report.record("matches", "created")
            else:
                self._refresh("matches", self.matches, entity, values)
            self.match_refs.create(
                {
                    "provider": self.provider,
                    "external_id": external_id,
                    "match_id": entity.id,
                }
            )
        else:
            self._refresh("matches", self.matches, entity, values)
        return entity

    def _lineup(self, values: dict[str, Any]) -> None:
        match_id = self._required_id(
            self.match_refs,
            values.pop("match_external_id"),
            "match_id",
            "match",
        )
        player_id = self._required_id(
            self.player_refs,
            values.pop("player_external_id"),
            "player_id",
            "player",
        )
        team_id = self._required_id(
            self.team_refs,
            values.pop("team_external_id"),
            "team_id",
            "team",
        )
        values.update(match_id=match_id, player_id=player_id, team_id=team_id)
        entity = self.lineups.get_by(match_id=match_id, player_id=player_id)
        self._create_or_refresh("lineups", self.lineups, entity, values)

    def _player_match_stats(self, values: dict[str, Any]) -> None:
        match_id = self._required_id(
            self.match_refs,
            values.pop("match_external_id"),
            "match_id",
            "match",
        )
        player_id = self._required_id(
            self.player_refs,
            values.pop("player_external_id"),
            "player_id",
            "player",
        )
        values.update(match_id=match_id, player_id=player_id)
        entity = self.player_stats.get_by(match_id=match_id, player_id=player_id)
        self._create_or_refresh(
            "player_match_stats", self.player_stats, entity, values
        )

    def _matchup_event(self, values: dict[str, Any]) -> None:
        match_id = self._required_id(
            self.match_refs,
            values.pop("match_external_id"),
            "match_id",
            "match",
        )
        attacker_id = self._required_id(
            self.player_refs,
            values.pop("attacker_external_id"),
            "player_id",
            "attacker",
        )
        defender_id = self._required_id(
            self.player_refs,
            values.pop("defender_external_id"),
            "player_id",
            "defender",
        )
        values.update(
            match_id=match_id, attacker_id=attacker_id, defender_id=defender_id
        )
        entity = self.matchup_events.get_by(
            match_id=match_id, attacker_id=attacker_id, defender_id=defender_id
        )
        self._create_or_refresh(
            "matchup_events", self.matchup_events, entity, values
        )

    def _spatial_event(self, values: dict[str, Any]) -> None:
        external_id = values.pop("external_id")
        match_id = self._required_id(self.match_refs, values.pop("match_external_id"), "match_id", "match")
        team_id = self._required_id(self.team_refs, values.pop("team_external_id"), "team_id", "team")
        player_id = self._required_id(self.player_refs, values.pop("player_external_id"), "player_id", "player")
        values.update(
            provider=self.provider,
            external_id=external_id,
            match_id=match_id,
            team_id=team_id,
            player_id=player_id,
        )
        entity = self.spatial_events.get_by(provider=self.provider, external_id=external_id)
        self._create_or_refresh("spatial_events", self.spatial_events, entity, values)
