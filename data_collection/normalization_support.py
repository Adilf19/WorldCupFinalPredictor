"""Shared identity resolution and change-reporting support for normalization."""

from dataclasses import dataclass, field
from typing import Any, TypeVar

from database.base import Base
from database.crud import Repository
from data_collection.providers.base import validate_provider_key

EntityT = TypeVar("EntityT", bound=Base)


class NormalizationError(RuntimeError):
    """Base error for provider-to-ORM normalization failures."""


class AmbiguousIdentityError(NormalizationError):
    """Raised when a new provider ID matches multiple canonical entities."""


class UnresolvedReferenceError(NormalizationError):
    """Raised when a provider relation cannot resolve its canonical entity."""


@dataclass(slots=True)
class EntityChanges:
    """Change counts for one ORM entity type."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0


@dataclass(slots=True)
class NormalizationReport:
    """Auditable summary of one provider normalization run."""

    provider: str
    changes: dict[str, EntityChanges] = field(default_factory=dict)

    def record(self, entity: str, outcome: str) -> None:
        counts = self.changes.setdefault(entity, EntityChanges())
        setattr(counts, outcome, getattr(counts, outcome) + 1)

    @property
    def total_created(self) -> int:
        return sum(change.created for change in self.changes.values())

    @property
    def total_updated(self) -> int:
        return sum(change.updated for change in self.changes.values())


class NormalizationSupport:
    """Provider reference resolution and common persistence policies."""

    def __init__(self, *, provider: str) -> None:
        self.provider = validate_provider_key(provider)
        self.report = NormalizationReport(provider=self.provider)

    def _by_reference(
        self,
        reference_repository: Repository[Any],
        entity_repository: Repository[EntityT],
        external_id: str,
        entity_id_field: str,
    ) -> EntityT | None:
        reference = reference_repository.get_by(
            provider=self.provider, external_id=external_id
        )
        if reference is None:
            return None
        entity_id = getattr(reference, entity_id_field)
        entity = entity_repository.get(entity_id)
        if entity is None:
            raise UnresolvedReferenceError(
                f"Dangling {self.provider}:{external_id} provider reference"
            )
        return entity

    def _required_id(
        self,
        repository: Repository[Any],
        external_id: str,
        entity_id_field: str,
        label: str,
    ) -> int:
        reference = repository.get_by(
            provider=self.provider, external_id=external_id
        )
        if reference is None:
            raise UnresolvedReferenceError(
                f"Unknown {label} reference {self.provider}:{external_id}"
            )
        return int(getattr(reference, entity_id_field))

    @staticmethod
    def _find_unique(
        repository: Repository[EntityT], *, entity_name: str, **filters: Any
    ) -> EntityT | None:
        matches = repository.list(limit=2, **filters)
        if len(matches) > 1:
            raise AmbiguousIdentityError(
                f"Multiple {entity_name} rows match natural identity {filters!r}"
            )
        return matches[0] if matches else None

    def _fill_missing(
        self,
        label: str,
        repository: Repository[EntityT],
        entity: EntityT,
        values: dict[str, Any],
    ) -> None:
        updates = {
            key: value
            for key, value in values.items()
            if getattr(entity, key) is None and value is not None
        }
        if updates:
            repository.update(entity, updates)
            self.report.record(label, "updated")
        else:
            self.report.record(label, "unchanged")

    def _refresh(
        self,
        label: str,
        repository: Repository[EntityT],
        entity: EntityT,
        values: dict[str, Any],
    ) -> None:
        updates = {
            key: value
            for key, value in values.items()
            if value is not None and getattr(entity, key) != value
        }
        if updates:
            repository.update(entity, updates)
            self.report.record(label, "updated")
        else:
            self.report.record(label, "unchanged")

    def _create_or_refresh(
        self,
        label: str,
        repository: Repository[EntityT],
        entity: EntityT | None,
        values: dict[str, Any],
    ) -> None:
        if entity is None:
            repository.create(values)
            self.report.record(label, "created")
        else:
            self._refresh(label, repository, entity, values)
