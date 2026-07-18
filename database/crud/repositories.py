"""Model-specific repository entry points.

These intentionally remain thin. They give services stable, discoverable types
and provide a natural home for domain-specific queries as the platform grows.
"""

from database.crud.base import Repository
from database.models import (
    Competition,
    CompetitionProviderReference,
    Lineup,
    Manager,
    ManagerHistory,
    Match,
    MatchProviderReference,
    MatchupEvent,
    Player,
    PlayerEmbedding,
    PlayerMatchStat,
    PlayerProviderReference,
    Prediction,
    OwnerLoginChallenge,
    OwnerSession,
    SelectedFixture,
    SimulationResult,
    SpatialEvent,
    Team,
    TeamPlayer,
    TeamProviderReference,
)


class CompetitionRepository(Repository[Competition]):
    model = Competition


class TeamRepository(Repository[Team]):
    model = Team


class PlayerRepository(Repository[Player]):
    model = Player


class TeamPlayerRepository(Repository[TeamPlayer]):
    model = TeamPlayer


class MatchRepository(Repository[Match]):
    model = Match


class LineupRepository(Repository[Lineup]):
    model = Lineup


class PlayerMatchStatRepository(Repository[PlayerMatchStat]):
    model = PlayerMatchStat


class MatchupEventRepository(Repository[MatchupEvent]):
    model = MatchupEvent


class SpatialEventRepository(Repository[SpatialEvent]):
    model = SpatialEvent


class PlayerEmbeddingRepository(Repository[PlayerEmbedding]):
    model = PlayerEmbedding


class ManagerRepository(Repository[Manager]):
    model = Manager


class ManagerHistoryRepository(Repository[ManagerHistory]):
    model = ManagerHistory


class PredictionRepository(Repository[Prediction]):
    model = Prediction


class SimulationResultRepository(Repository[SimulationResult]):
    model = SimulationResult


class OwnerLoginChallengeRepository(Repository[OwnerLoginChallenge]):
    model = OwnerLoginChallenge


class OwnerSessionRepository(Repository[OwnerSession]):
    model = OwnerSession


class SelectedFixtureRepository(Repository[SelectedFixture]):
    model = SelectedFixture


class CompetitionProviderReferenceRepository(
    Repository[CompetitionProviderReference]
):
    model = CompetitionProviderReference


class TeamProviderReferenceRepository(Repository[TeamProviderReference]):
    model = TeamProviderReference


class PlayerProviderReferenceRepository(Repository[PlayerProviderReference]):
    model = PlayerProviderReference


class MatchProviderReferenceRepository(Repository[MatchProviderReference]):
    model = MatchProviderReference
