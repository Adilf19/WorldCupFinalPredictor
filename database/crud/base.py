"""Typed, transaction-neutral CRUD operations for SQLAlchemy models."""

from collections.abc import Mapping, Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from database.base import Base
from database.crud.exceptions import EntityNotFoundError, InvalidFieldError

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    """Reusable CRUD repository for one mapped model.

    Repositories flush changes but never commit them. The calling service owns
    transaction boundaries, allowing multiple writes to succeed or fail as one.
    """

    model: type[ModelT]
    default_page_size = 100
    max_page_size = 500

    def __init__(self, session: Session) -> None:
        if not hasattr(self, "model"):
            raise TypeError("Repository subclasses must define a model")
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        """Return an entity by primary key, or ``None`` when absent."""
        return self.session.get(self.model, entity_id)

    def get_or_raise(self, entity_id: int) -> ModelT:
        """Return an entity by primary key or raise a stable repository error."""
        entity = self.get(entity_id)
        if entity is None:
            raise EntityNotFoundError(self.model.__name__, entity_id)
        return entity

    def get_by(self, **filters: Any) -> ModelT | None:
        """Return the first row matching equality filters."""
        self._validate_fields(filters, writable=False)
        statement = select(self.model).filter_by(**filters).limit(1)
        return self.session.scalars(statement).first()

    def list(
        self,
        *,
        offset: int = 0,
        limit: int | None = None,
        order_by: str = "id",
        **filters: Any,
    ) -> Sequence[ModelT]:
        """Return a bounded page matching equality filters.

        Prefix ``order_by`` with ``-`` for descending order, for example
        ``order_by="-created_at"``.
        """
        page_size = self.default_page_size if limit is None else limit
        self._validate_pagination(offset=offset, limit=page_size)
        self._validate_fields(filters, writable=False)

        descending = order_by.startswith("-")
        order_field = order_by[1:] if descending else order_by
        self._validate_fields({order_field: None}, writable=False)
        order_column = getattr(self.model, order_field)
        ordering = order_column.desc() if descending else order_column.asc()

        statement = (
            select(self.model)
            .filter_by(**filters)
            .order_by(ordering)
            .offset(offset)
            .limit(page_size)
        )
        return self.session.scalars(statement).all()

    def count(self, **filters: Any) -> int:
        """Count rows matching equality filters."""
        self._validate_fields(filters, writable=False)
        statement = select(func.count()).select_from(self.model).filter_by(**filters)
        return self.session.scalar(statement) or 0

    def exists(self, **filters: Any) -> bool:
        """Return whether at least one row matches equality filters."""
        self._validate_fields(filters, writable=False)
        statement = select(select(self.model).filter_by(**filters).exists())
        return bool(self.session.scalar(statement))

    def create(self, values: Mapping[str, Any]) -> ModelT:
        """Create and flush an entity without committing the transaction."""
        self._validate_fields(values, writable=True)
        entity = self.model(**dict(values))
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def update(self, entity: ModelT, values: Mapping[str, Any]) -> ModelT:
        """Apply fields to a persistent entity and flush without committing."""
        self._ensure_model_instance(entity)
        self._validate_fields(values, writable=True)
        for field, value in values.items():
            setattr(entity, field, value)
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def update_by_id(self, entity_id: int, values: Mapping[str, Any]) -> ModelT:
        """Update an entity by primary key or raise when it does not exist."""
        return self.update(self.get_or_raise(entity_id), values)

    def delete(self, entity: ModelT) -> None:
        """Delete a persistent entity and flush without committing."""
        self._ensure_model_instance(entity)
        self.session.delete(entity)
        self.session.flush()

    def delete_by_id(self, entity_id: int) -> None:
        """Delete an entity by primary key or raise when it does not exist."""
        self.delete(self.get_or_raise(entity_id))

    def _validate_fields(self, values: Mapping[str, Any], *, writable: bool) -> None:
        mapper = inspect(self.model)
        valid_fields = {attribute.key for attribute in mapper.column_attrs}
        invalid_fields = set(values) - valid_fields
        if invalid_fields:
            raise InvalidFieldError(self.model.__name__, invalid_fields)

        if writable:
            primary_keys = {column.key for column in mapper.primary_key}
            supplied_primary_keys = set(values) & primary_keys
            if supplied_primary_keys:
                raise InvalidFieldError(self.model.__name__, supplied_primary_keys)

    def _ensure_model_instance(self, entity: ModelT) -> None:
        if not isinstance(entity, self.model):
            raise TypeError(
                f"Expected {self.model.__name__}, received {type(entity).__name__}"
            )

    def _validate_pagination(self, *, offset: int, limit: int) -> None:
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")
        if not 1 <= limit <= self.max_page_size:
            raise ValueError(f"limit must be between 1 and {self.max_page_size}")
