"""Tests for the 2026 World Cup final reference-data seeder."""

import unittest

from sqlalchemy.orm import Session

from database.connection import engine
from database.seeding import WorldCupFinalSeeder
from seed_data.world_cup_2026 import ARGENTINA, SPAIN


class SeedDataTests(unittest.TestCase):
    def test_each_finalist_has_26_unique_players(self) -> None:
        for team in (SPAIN, ARGENTINA):
            names = [player.name for player in team.players]
            self.assertEqual(len(names), 26)
            self.assertEqual(len(set(names)), 26)


class SeederPostgresTests(unittest.TestCase):
    def test_seed_is_idempotent(self) -> None:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                WorldCupFinalSeeder(session).seed()
                second_run = WorldCupFinalSeeder(session).seed()
                self.assertEqual(second_run.total_created, 0)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
