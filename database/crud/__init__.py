"""Public CRUD repository interface."""

from database.crud.base import Repository
from database.crud.exceptions import EntityNotFoundError, InvalidFieldError, RepositoryError
from database.crud.repositories import (
    CompetitionRepository,
    CompetitionProviderReferenceRepository,
    LineupRepository,
    ManagerHistoryRepository,
    ManagerRepository,
    MatchRepository,
    MatchProviderReferenceRepository,
    MatchupEventRepository,
    PlayerEmbeddingRepository,
    PlayerMatchStatRepository,
    PlayerRepository,
    PlayerProviderReferenceRepository,
    PredictionRepository,
    SimulationResultRepository,
    SpatialEventRepository,
    TeamPlayerRepository,
    TeamProviderReferenceRepository,
    TeamRepository,
)

__all__ = [
    "CompetitionRepository",
    "CompetitionProviderReferenceRepository",
    "EntityNotFoundError",
    "InvalidFieldError",
    "LineupRepository",
    "ManagerHistoryRepository",
    "ManagerRepository",
    "MatchRepository",
    "MatchProviderReferenceRepository",
    "MatchupEventRepository",
    "PlayerEmbeddingRepository",
    "PlayerMatchStatRepository",
    "PlayerRepository",
    "PlayerProviderReferenceRepository",
    "PredictionRepository",
    "Repository",
    "RepositoryError",
    "SimulationResultRepository",
    "SpatialEventRepository",
    "TeamPlayerRepository",
    "TeamProviderReferenceRepository",
    "TeamRepository",
]
