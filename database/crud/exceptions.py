"""Domain-neutral errors raised by database CRUD utilities."""


class RepositoryError(Exception):
    """Base class for repository failures that callers may handle."""


class InvalidFieldError(RepositoryError, ValueError):
    """Raised when a CRUD payload references an unmapped model field."""

    def __init__(self, model_name: str, fields: set[str]) -> None:
        field_list = ", ".join(sorted(fields))
        super().__init__(f"Invalid field(s) for {model_name}: {field_list}")
        self.model_name = model_name
        self.fields = frozenset(fields)


class EntityNotFoundError(RepositoryError, LookupError):
    """Raised when an entity required by an operation does not exist."""

    def __init__(self, model_name: str, entity_id: object) -> None:
        super().__init__(f"{model_name} with id={entity_id!r} was not found")
        self.model_name = model_name
        self.entity_id = entity_id
