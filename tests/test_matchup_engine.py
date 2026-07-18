"""Tests for expected-lineup and positional-matchup prediction."""

import unittest
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from database.connection import engine
from database.crud import (
    CompetitionRepository,
    LineupRepository,
    MatchRepository,
    MatchupEventRepository,
    PlayerRepository,
    TeamPlayerRepository,
    TeamRepository,
)
from database.models import Player
from matchup_engine import MatchupPredictionPipeline, PredictorConfig
from matchup_engine.matchup_scorer import AttributeMatchupScorer
from matchup_engine.h2h_engine import DirectH2HEngine
from matchup_engine.positions import position_compatibility
from matchup_engine.spatial_matchup import SpatialMatchupPredictor
from matchup_engine.similarity_engine import PlayerFingerprint, PlayerSimilarityEngine


class PositionCompatibilityTests(unittest.TestCase):
    def test_exact_and_broad_positions_are_supported(self) -> None:
        self.assertEqual(position_compatibility("RW", "RW"), 1.0)
        self.assertEqual(position_compatibility("FW", "ST"), 0.65)
        self.assertEqual(position_compatibility("GK", "ST"), 0.0)


class AttributeMatchupScorerTests(unittest.TestCase):
    def test_complete_attributes_produce_home_advantage(self) -> None:
        home = Player(
            name="Home Winger",
            pace=90,
            dribbling=90,
            creativity=85,
            passing=80,
            finishing=75,
        )
        away = Player(name="Away Fullback", defending=60, pace=65, strength=65)
        evidence = AttributeMatchupScorer().score(
            home_player=home,
            away_player=away,
            home_profile="wing_attack",
            away_profile="fullback_defense",
        )
        self.assertIsNotNone(evidence.home_advantage)
        self.assertGreater(float(evidence.home_advantage), 0)
        self.assertEqual(evidence.confidence, 1.0)

    def test_missing_attributes_are_not_replaced_with_zeroes(self) -> None:
        evidence = AttributeMatchupScorer().score(
            home_player=Player(name="Unknown Home"),
            away_player=Player(name="Unknown Away"),
            home_profile="striker_attack",
            away_profile="centreback_defense",
        )
        self.assertIsNone(evidence.home_advantage)
        self.assertEqual(evidence.confidence, 0.0)
        self.assertTrue(evidence.missing_dimensions)


class SpatialMathTests(unittest.TestCase):
    def test_opposition_heatmap_is_rotated_into_home_frame(self) -> None:
        predictor = object.__new__(SpatialMatchupPredictor)
        predictor.config = PredictorConfig(spatial_grid_columns=4, spatial_grid_rows=3)
        cells = tuple(float(index) for index in range(12))
        self.assertEqual(predictor._rotate(cells), tuple(reversed(cells)))

    def test_overlap_coefficient_is_bounded_and_symmetric(self) -> None:
        home = (0.5, 0.5, 0.0)
        away = (0.25, 0.5, 0.25)
        self.assertEqual(SpatialMatchupPredictor._overlap(home, away), 0.75)
        self.assertEqual(
            SpatialMatchupPredictor._overlap(home, away),
            SpatialMatchupPredictor._overlap(away, home),
        )


class SimilarityMathTests(unittest.TestCase):
    def test_role_compatible_fingerprint_scores_higher(self) -> None:
        values = {"mean_x": 0.5, "mean_y": 0.4, "pass_share": 0.7}
        target = PlayerFingerprint(Player(id=1, name="Target", primary_position="MF"), values, 100)
        midfielder = PlayerFingerprint(Player(id=2, name="Mid", primary_position="LCM"), values, 100)
        goalkeeper = PlayerFingerprint(Player(id=3, name="Keeper", primary_position="GK"), values, 100)
        self.assertGreater(
            PlayerSimilarityEngine._similarity(target, midfielder),
            PlayerSimilarityEngine._similarity(target, goalkeeper),
        )


class DirectH2HPostgresTests(unittest.TestCase):
    def test_provider_linked_duels_are_scored_before_cutoff(self) -> None:
        suffix = uuid4().hex
        cutoff = date(2026, 7, 19)
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                competition = CompetitionRepository(session).create({"name": f"H2H {suffix}"})
                home_team = TeamRepository(session).create({"name": f"H2H Home {suffix}"})
                away_team = TeamRepository(session).create({"name": f"H2H Away {suffix}"})
                home = PlayerRepository(session).create({"name": f"H2H Attacker {suffix}"})
                away = PlayerRepository(session).create({"name": f"H2H Defender {suffix}"})
                match = MatchRepository(session).create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff - timedelta(days=30),
                        "home_team": home_team.id,
                        "away_team": away_team.id,
                    }
                )
                MatchupEventRepository(session).create(
                    {
                        "match_id": match.id,
                        "attacker_id": home.id,
                        "defender_id": away.id,
                        "minutes_together": 90,
                        "attacking_duels_won": 8,
                        "attacking_duels_lost": 2,
                        "defensive_duels_won": 2,
                        "defensive_duels_lost": 8,
                    }
                )
                result = DirectH2HEngine(session).score(
                    home_player_id=home.id, away_player_id=away.id, as_of=cutoff
                )
                self.assertEqual(result.source, "direct_linked_duels")
                self.assertEqual(result.sample_matches, 1)
                self.assertGreater(float(result.home_advantage), 0)
                self.assertGreater(result.confidence, 0)
            finally:
                session.close()
                transaction.rollback()


class MatchupPipelinePostgresTests(unittest.TestCase):
    def test_pipeline_predicts_complete_lineups_and_matchups(self) -> None:
        suffix = uuid4().hex
        cutoff = date(2026, 7, 19)
        roles = PredictorConfig().formation_roles

        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            teams = TeamRepository(session)
            players = PlayerRepository(session)
            memberships = TeamPlayerRepository(session)
            lineups = LineupRepository(session)
            try:
                competition = CompetitionRepository(session).create(
                    {
                        "name": f"Matchup Competition {suffix}",
                        "country": "Test",
                    }
                )
                home_team = teams.create(
                    {"name": f"Matchup Home {suffix}", "country": "Test"}
                )
                away_team = teams.create(
                    {"name": f"Matchup Away {suffix}", "country": "Test"}
                )
                match = MatchRepository(session).create(
                    {
                        "competition_id": competition.id,
                        "date": cutoff - timedelta(days=10),
                        "home_team": home_team.id,
                        "away_team": away_team.id,
                        "home_goals": 2,
                        "away_goals": 1,
                    }
                )

                for team, level, prefix in (
                    (home_team, 80.0, "Home"),
                    (away_team, 60.0, "Away"),
                ):
                    for shirt_number, role in enumerate(roles, start=1):
                        player = players.create(
                            {
                                "name": f"{prefix} {role} {suffix}",
                                "nationality": "Test",
                                "primary_position": role,
                                "pace": level,
                                "strength": level,
                                "passing": level,
                                "dribbling": level,
                                "finishing": level,
                                "defending": level,
                                "creativity": level,
                            }
                        )
                        memberships.create(
                            {
                                "team_id": team.id,
                                "player_id": player.id,
                                "start_date": cutoff - timedelta(days=100),
                                "end_date": cutoff + timedelta(days=1),
                            }
                        )
                        lineups.create(
                            {
                                "match_id": match.id,
                                "player_id": player.id,
                                "team_id": team.id,
                                "position": role,
                                "shirt_number": shirt_number,
                                "starter": True,
                                "minutes_played": 90,
                            }
                        )

                prediction = MatchupPredictionPipeline(session).predict(
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    as_of=cutoff,
                )

                self.assertEqual(len(prediction.home_lineup.players), 11)
                self.assertEqual(len(prediction.away_lineup.players), 11)
                self.assertEqual(prediction.home_lineup.completeness, 1.0)
                self.assertEqual(prediction.home_lineup.evidence_coverage, 1.0)
                self.assertGreater(prediction.home_lineup.confidence, 0)
                self.assertEqual(len(prediction.battles), 13)
                self.assertIsNotNone(prediction.overall_home_advantage)
                self.assertGreater(float(prediction.overall_home_advantage), 0)
                self.assertGreater(prediction.evidence_coverage, 0)
                self.assertLess(prediction.evidence_coverage, 1)
                self.assertIsNotNone(prediction.biggest_differentiator)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
