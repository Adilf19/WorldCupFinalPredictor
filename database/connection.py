"""Database engine and session lifecycle configuration."""

import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def _database_url() -> str:
    """Return the configured database URL or fail with an actionable error."""
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not set. Add it to the environment or .env file.")
    return value


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    """Parse a conventional environment boolean."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


engine: Engine = create_engine(
    _database_url(),
    echo=_as_bool(os.getenv("DATABASE_ECHO")),
    pool_pre_ping=True,
)

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped session without deciding transaction outcome.

    This is suitable as a FastAPI dependency. Endpoint or service code owns the
    commit so multiple repository operations can form one atomic transaction.
    """
    with SessionFactory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session for scripts and background jobs."""
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
