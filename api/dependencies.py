"""FastAPI database transaction dependency."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from database.connection import SessionFactory


def get_db() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
