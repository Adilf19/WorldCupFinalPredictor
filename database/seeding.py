"""Idempotent reference-data seeding services."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.crud import (
    CompetitionRepository,
    ManagerRepository,
    MatchRepository,
    PlayerRepository,
    TeamPlayerRepository,
    TeamRepository,
)
from database.models import Competition, Manager, Match, Player, Team
from seed_data.world_cup_2026 import (
    ARGENTINA,
    FINAL_DATE,
    FINAL_VENUE,
    FINALISTS,
    SPAIN,
    SQUAD_END_DATE,
    SQUAD_START_DATE,
    TeamSeed,
)


class SeedConflictError(RuntimeError):
    """Raised when existing identity data conflicts with authoritative seed data."""


@dataclass(slots=True)
class SeedSummary:
    """Counts of records created during a seed run."""

    competitions_created: int = 0
    teams_created: int = 0
    managers_created: int = 0
    players_created: int = 0
    memberships_created: int = 0
    matches_created: int = 0

    @property
    def total_created(self) -> int:
        """Return the total number of inserted rows."""
        return sum(
            (
                self.competitions_created,
                self.teams_created,
                self.managers_created,
                self.players_created,
                self.memberships_created,
                self.matches_created,
            )
        )


class WorldCupFinalSeeder:
    """Seed the 2026 Spain–Argentina final and both tournament squads."""

    def __init__(self, session: Session) -> None:
        self.competitions = CompetitionRepository(session)
        self.teams = TeamRepository(session)
        self.managers = ManagerRepository(session)
        self.players = PlayerRepository(session)
        self.memberships = TeamPlayerRepository(session)
        self.matches = MatchRepository(session)
        self.summary = SeedSummary()

    def seed(self) -> SeedSummary:
        """Upsert all reference records and return insertion counts."""
        competition = self._seed_competition()
        seeded_teams = {
            team_seed.name: self._seed_team(team_seed) for team_seed in FINALISTS
        }
        self._seed_final(
            competition=competition,
            home_team=seeded_teams[SPAIN.name],
            away_team=seeded_teams[ARGENTINA.name],
        )
        return self.summary

    def _seed_competition(self) -> Competition:
        competition = self.competitions.get_by(
            name="FIFA World Cup 2026", country="International"
        )
        if competition is not None:
            return competition

        self.summary.competitions_created += 1
        return self.competitions.create(
            {
                "name": "FIFA World Cup 2026",
                "country": "International",
                "competition_type": "international",
                "format": "hybrid",
                "team_type": "country",
                "competition_tier": 1.0,
            }
        )

    def _seed_team(self, seed: TeamSeed) -> Team:
        team = self.teams.get_by(name=seed.name)
        if team is None:
            team = self.teams.create(
                {"name": seed.name, "country": seed.country, "team_type": "country", "manager": seed.manager}
            )
            self.summary.teams_created += 1
        else:
            self._validate_identity("Team", seed.name, team.country, seed.country)
            updates: dict[str, object] = {}
            if team.country is None:
                updates["country"] = seed.country
            if team.manager != seed.manager:
                updates["manager"] = seed.manager
            if updates:
                self.teams.update(team, updates)

        self._seed_manager(seed)
        for player_seed in seed.players:
            player = self._seed_player(
                name=player_seed.name,
                nationality=seed.country,
                position=player_seed.position,
            )
            if not self.memberships.exists(
                team_id=team.id,
                player_id=player.id,
                start_date=SQUAD_START_DATE,
            ):
                self.memberships.create(
                    {
                        "team_id": team.id,
                        "player_id": player.id,
                        "start_date": SQUAD_START_DATE,
                        "end_date": SQUAD_END_DATE,
                    }
                )
                self.summary.memberships_created += 1
        return team

    def _seed_manager(self, seed: TeamSeed) -> Manager:
        manager = self.managers.get_by(name=seed.manager)
        if manager is not None:
            return manager
        self.summary.managers_created += 1
        return self.managers.create({"name": seed.manager})

    def _seed_player(self, *, name: str, nationality: str, position: str) -> Player:
        player = self.players.get_by(name=name)
        if player is None:
            self.summary.players_created += 1
            return self.players.create(
                {
                    "name": name,
                    "nationality": nationality,
                    "primary_position": position,
                }
            )

        self._validate_identity("Player", name, player.nationality, nationality)
        updates: dict[str, object] = {}
        if player.nationality is None:
            updates["nationality"] = nationality
        if player.primary_position is None:
            updates["primary_position"] = position
        if updates:
            self.players.update(player, updates)
        return player

    def _seed_final(
        self, *, competition: Competition, home_team: Team, away_team: Team
    ) -> Match:
        match = self.matches.get_by(
            competition_id=competition.id,
            date=FINAL_DATE,
            home_team=home_team.id,
            away_team=away_team.id,
        )
        if match is not None:
            if match.venue is None:
                self.matches.update(match, {"venue": FINAL_VENUE})
            return match

        self.summary.matches_created += 1
        return self.matches.create(
            {
                "competition_id": competition.id,
                "date": FINAL_DATE,
                "home_team": home_team.id,
                "away_team": away_team.id,
                "venue": FINAL_VENUE,
                "stage": "FINAL",
                "is_knockout": True,
            }
        )

    @staticmethod
    def _validate_identity(
        entity_type: str,
        name: str,
        existing_value: str | None,
        expected_value: str,
    ) -> None:
        if existing_value not in {None, expected_value}:
            raise SeedConflictError(
                f"{entity_type} {name!r} has conflicting identity value "
                f"{existing_value!r}; expected {expected_value!r}"
            )
