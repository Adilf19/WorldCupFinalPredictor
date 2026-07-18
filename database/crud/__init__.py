"""Public CRUD repository interface."""

from database.crud.base import Repository
from database.crud.exceptions import EntityNotFoundError, InvalidFieldError, RepositoryError
from database.crud.repositories import (
    CompetitionRepository,
    LineupRepository,
    ManagerHistoryRepository,
    ManagerRepository,
    MatchRepository,
    MatchupEventRepository,
    PlayerEmbeddingRepository,
    PlayerMatchStatRepository,
    PlayerRepository,
    PredictionRepository,
    SimulationResultRepository,
    TeamPlayerRepository,
    TeamRepository,
)

__all__ = [
    "CompetitionRepository",
    "EntityNotFoundError",
    "InvalidFieldError",
    "LineupRepository",
    "ManagerHistoryRepository",
    "ManagerRepository",
    "MatchRepository",
    "MatchupEventRepository",
    "PlayerEmbeddingRepository",
    "PlayerMatchStatRepository",
    "PlayerRepository",
    "PredictionRepository",
    "Repository",
    "RepositoryError",
    "SimulationResultRepository",
    "TeamPlayerRepository",
    "TeamRepository",
]
