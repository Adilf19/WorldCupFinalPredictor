"""CRUD repository tests, including a rolled-back PostgreSQL lifecycle."""

import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from database.connection import engine
from database.crud import (
    CompetitionRepository,
    EntityNotFoundError,
    InvalidFieldError,
)


class RepositoryValidationTests(unittest.TestCase):
    """Validate failures that do not require a database connection."""

    def setUp(self) -> None:
        self.repository = CompetitionRepository(Session())

    def tearDown(self) -> None:
        self.repository.session.close()

    def test_rejects_unknown_filter_field(self) -> None:
        with self.assertRaises(InvalidFieldError):
            self.repository.get_by(unknown_field="value")

    def test_rejects_primary_key_in_create_payload(self) -> None:
        with self.assertRaises(InvalidFieldError):
            self.repository.create({"id": 123, "name": "Invalid"})

    def test_rejects_unbounded_page_size(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.list(limit=501)


class RepositoryPostgresLifecycleTests(unittest.TestCase):
    """Exercise writes against PostgreSQL and always roll them back."""

    def test_create_read_update_list_count_and_delete(self) -> None:
        unique_name = f"CRUD test {uuid4()}"

        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            repository = CompetitionRepository(session)
            try:
                created = repository.create(
                    {
                        "name": unique_name,
                        "country": "Test",
                        "competition_type": "test",
                    }
                )
                self.assertIsNotNone(created.id)
                self.assertEqual(repository.get(created.id), created)
                self.assertEqual(repository.get_by(name=unique_name), created)
                self.assertTrue(repository.exists(name=unique_name))
                self.assertEqual(repository.count(name=unique_name), 1)
                self.assertEqual(repository.list(name=unique_name), [created])

                updated = repository.update_by_id(
                    created.id, {"competition_tier": 0.75}
                )
                self.assertEqual(updated.competition_tier, 0.75)

                repository.delete_by_id(created.id)
                self.assertFalse(repository.exists(name=unique_name))
                with self.assertRaises(EntityNotFoundError):
                    repository.get_or_raise(created.id)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
