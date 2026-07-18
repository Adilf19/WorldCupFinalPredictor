"""Unit and PostgreSQL integration tests for team feature engineering."""

import unittest
from datetime import date, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from database.connection import engine
from database.crud import CompetitionRepository, MatchRepository, TeamRepository
from feature_engineering import MatchFeaturePipeline, TeamFeatureConfig
from feature_engineering.weighting import (
    effective_sample_size,
    recency_weight,
    weighted_average,
)


class WeightingTests(unittest.TestCase):
    def test_recency_weight_halves_at_half_life(self) -> None:
        self.assertAlmostEqual(
            recency_weight(age_days=180, half_life_days=180), 0.5
        )

    def test_weighted_average_ignores_missing_values(self) -> None:
        self.assertEqual(weighted_average([(None, 100), (4.0, 2)]), 4.0)

    def test_effective_sample_size_reflects_unequal_weights(self) -> None:
        self.assertAlmostEqual(effective_sample_size([1, 1]), 2.0)
        self.assertLess(effective_sample_size([1, 0.1]), 2.0)

    def test_config_rejects_zero_lookback(self) -> None:
        with self.assertRaises(ValidationError):
            TeamFeatureConfig(lookback_matches=0)


class TeamFeaturePipelinePostgresTests(unittest.TestCase):
    def test_pipeline_normalizes_perspective_weights_and_deltas(self) -> None:
        suffix = uuid4().hex
        cutoff = date(2026, 7, 19)

        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            teams = TeamRepository(session)
            competitions = CompetitionRepository(session)
            matches = MatchRepository(session)
            try:
                competition = competitions.create(
                    {
                        "name": f"Feature Competition {suffix}",
                        "country": "Test",
                        "competition_tier": 1.0,
                    }
                )
                home_team = teams.create(
                    {
                        "name": f"Feature Home {suffix}",
                        "country": "Test",
                        "elo_rating": 1900.0,
                        "fifa_ranking": 2,
                    }
                )
                away_team = teams.create(
                    {
                        "name": f"Feature Away {suffix}",
                        "country": "Test",
                        "elo_rating": 1800.0,
                        "fifa_ranking": 8,
                    }
                )

                matches.create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff - timedelta(days=10),
                        "home_team": home_team.id,
                        "away_team": away_team.id,
                        "home_goals": 2,
                        "away_goals": 0,
                        "home_xg": 2.0,
                        "away_xg": 0.5,
                        "home_possession": 60.0,
                        "away_possession": 40.0,
                        "home_shots": 15,
                        "away_shots": 5,
                        "home_pass_accuracy": 90.0,
                        "away_pass_accuracy": 80.0,
                    }
                )
                matches.create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff - timedelta(days=190),
                        "home_team": away_team.id,
                        "away_team": home_team.id,
                        "home_goals": 1,
                        "away_goals": 0,
                        "home_xg": 1.2,
                        "away_xg": 0.8,
                        "home_possession": 55.0,
                        "away_possession": 45.0,
                        "home_shots": 10,
                        "away_shots": 7,
                        "home_pass_accuracy": 86.0,
                        "away_pass_accuracy": 82.0,
                    }
                )
                # Same-day and incomplete matches must not leak into the vector.
                matches.create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff,
                        "home_team": home_team.id,
                        "away_team": away_team.id,
                        "home_goals": 9,
                        "away_goals": 0,
                    }
                )
                matches.create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff - timedelta(days=1),
                        "home_team": home_team.id,
                        "away_team": away_team.id,
                    }
                )

                comparison = MatchFeaturePipeline(
                    session,
                    config=TeamFeatureConfig(
                        lookback_matches=10,
                        recency_half_life_days=180,
                    ),
                ).build(
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    as_of=cutoff,
                )

                recent_weight = recency_weight(age_days=10, half_life_days=180)
                old_weight = recency_weight(age_days=190, half_life_days=180)
                expected_win_rate = recent_weight / (recent_weight + old_weight)

                self.assertEqual(comparison.home.matches_considered, 2)
                self.assertAlmostEqual(comparison.home.win_rate, expected_win_rate)
                self.assertAlmostEqual(
                    comparison.home.points_per_match, 3 * expected_win_rate
                )
                self.assertAlmostEqual(
                    comparison.home.home_match_share, expected_win_rate
                )
                self.assertEqual(comparison.home.statistics_coverage, 1.0)
                self.assertEqual(comparison.deltas.elo_rating, 100.0)
                self.assertEqual(comparison.deltas.fifa_rank_advantage, 6.0)
                self.assertIn("home_xg_for", comparison.model_features())
                self.assertIn("delta_goal_difference", comparison.model_features())
            finally:
                session.close()
                transaction.rollback()

    def test_pipeline_reports_missing_history_without_fabricating_values(self) -> None:
        suffix = uuid4().hex
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                team = TeamRepository(session).create(
                    {"name": f"No History {suffix}", "country": "Test"}
                )
                vector = MatchFeaturePipeline(session).team_features.build(
                    team_id=team.id, as_of=date(2026, 7, 19)
                )
                self.assertEqual(vector.matches_considered, 0)
                self.assertIsNone(vector.points_per_match)
                self.assertIsNone(vector.xg_for)
                self.assertEqual(vector.statistics_coverage, 0.0)
                self.assertEqual(vector.sample_confidence, 0.0)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
