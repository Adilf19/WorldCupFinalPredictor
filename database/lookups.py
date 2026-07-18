"""Reusable canonical-entity lookup helpers for scripts and services."""

from database.crud import TeamRepository
from database.models import Team


def unique_team_by_name(repository: TeamRepository, name: str) -> Team:
    """Return one canonical team or raise for missing/ambiguous names."""
    matches = repository.list(limit=2, name=name)
    if not matches:
        raise LookupError(f"Team {name!r} was not found")
    if len(matches) > 1:
        raise LookupError(f"Team name {name!r} is ambiguous")
    return matches[0]
