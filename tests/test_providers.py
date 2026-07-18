"""Provider contract, adapter, and ORM normalization tests."""

import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from data_collection.contracts import ProviderSnapshot
from data_collection.ingestion import ingest_provider
from data_collection.normalization import ProviderNormalizer, UnresolvedReferenceError
from data_collection.providers import JsonFileProvider
from data_collection.providers.football_data import competition_context
from database.connection import engine


class FootballDataContextTests(unittest.TestCase):
    def test_league_is_club_regulation_context(self) -> None:
        self.assertEqual(
            competition_context({"name": "Premier League", "type": "LEAGUE"}),
            ("league", "club"),
        )

    def test_world_cup_is_country_hybrid_context(self) -> None:
        self.assertEqual(
            competition_context({"name": "FIFA World Cup", "type": "CUP"}),
            ("hybrid", "country"),
        )


def _snapshot_payload(suffix: str) -> dict[str, object]:
    return {
        "competitions": [
            {
                "external_id": "competition-1",
                "name": f"Provider Test Competition {suffix}",
                "country": "Test",
            }
        ],
        "teams": [
            {
                "external_id": "team-home",
                "name": f"Provider Home {suffix}",
                "country": "Test",
            },
            {
                "external_id": "team-away",
                "name": f"Provider Away {suffix}",
                "country": "Test",
            },
        ],
        "players": [
            {
                "external_id": "player-home",
                "name": f"Provider Player Home {suffix}",
                "nationality": "Test",
                "primary_position": "FW",
            },
            {
                "external_id": "player-away",
                "name": f"Provider Player Away {suffix}",
                "nationality": "Test",
                "primary_position": "DF",
            },
        ],
        "matches": [
            {
                "external_id": "match-1",
                "competition_external_id": "competition-1",
                "home_team_external_id": "team-home",
                "away_team_external_id": "team-away",
                "date": date.today().isoformat(),
                "home_goals": 1,
                "away_goals": 0,
            }
        ],
        "player_availability": [
            {
                "external_id": "availability-home-1",
                "player_external_id": "player-home",
                "team_external_id": "team-home",
                "status": "doubtful",
                "reason": "Late fitness test",
                "reported_at": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.8,
            }
        ],
        "lineups": [
            {
                "match_external_id": "match-1",
                "player_external_id": "player-home",
                "team_external_id": "team-home",
                "starter": True,
                "minutes_played": 90,
            }
        ],
        "player_match_stats": [
            {
                "match_external_id": "match-1",
                "player_external_id": "player-home",
                "minutes": 90,
                "goals": 1,
                "rating": 8.2,
            }
        ],
        "matchup_events": [
            {
                "match_external_id": "match-1",
                "attacker_external_id": "player-home",
                "defender_external_id": "player-away",
                "minutes_together": 80,
                "attacking_duels_won": 3,
            }
        ],
        "spatial_events": [
            {
                "external_id": "event-1",
                "match_external_id": "match-1",
                "team_external_id": "team-home",
                "player_external_id": "player-home",
                "event_type": "Pass",
                "period": 1,
                "minute": 12,
                "x": 0.25,
                "y": 0.75,
                "end_x": 0.5,
                "end_y": 0.7,
            }
        ],
    }


class ProviderContractTests(unittest.TestCase):
    def test_contract_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSnapshot.model_validate({"unknown": []})

    def test_contract_rejects_duplicate_external_ids(self) -> None:
        payload = _snapshot_payload("duplicate")
        payload["teams"] = [payload["teams"][0], payload["teams"][0]]  # type: ignore[index]
        with self.assertRaises(ValidationError):
            ProviderSnapshot.model_validate(payload)

    def test_json_provider_loads_validated_snapshot(self) -> None:
        payload = _snapshot_payload("json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            provider = JsonFileProvider(path, provider_key="json_test")
            snapshot = asyncio.run(provider.fetch_snapshot())
        self.assertEqual(len(snapshot.teams), 2)
        self.assertEqual(snapshot.matches[0].external_id, "match-1")
        self.assertEqual(snapshot.spatial_events[0].x, 0.25)
        self.assertEqual(snapshot.player_availability[0].status, "doubtful")


class ProviderNormalizationPostgresTests(unittest.TestCase):
    def test_normalization_is_idempotent_and_updates_match_data(self) -> None:
        suffix = uuid4().hex
        provider_key = f"test_{suffix}"
        snapshot = ProviderSnapshot.model_validate(_snapshot_payload(suffix))

        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                class SnapshotProvider(JsonFileProvider):
                    async def fetch_snapshot(self) -> ProviderSnapshot:
                        return snapshot

                provider = SnapshotProvider(
                    Path("unused.json"), provider_key=provider_key
                )
                first = asyncio.run(ingest_provider(provider, session=session))
                second = ProviderNormalizer(
                    session, provider=provider_key
                ).normalize(snapshot)

                self.assertGreater(first.total_created, 0)
                self.assertEqual(second.total_created, 0)
                self.assertEqual(second.total_updated, 0)

                updated_payload = _snapshot_payload(suffix)
                updated_payload["matches"][0]["home_goals"] = 2  # type: ignore[index]
                updated = ProviderNormalizer(
                    session, provider=provider_key
                ).normalize(ProviderSnapshot.model_validate(updated_payload))
                self.assertEqual(updated.changes["matches"].updated, 1)
            finally:
                session.close()
                transaction.rollback()

    def test_unresolved_incremental_reference_raises(self) -> None:
        snapshot = ProviderSnapshot.model_validate(
            {
                "matches": [
                    {
                        "external_id": "missing-match",
                        "competition_external_id": "missing-competition",
                        "home_team_external_id": "missing-home",
                        "away_team_external_id": "missing-away",
                        "date": "2026-07-19",
                    }
                ]
            }
        )
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection)
            try:
                with self.assertRaises(UnresolvedReferenceError):
                    ProviderNormalizer(
                        session, provider=f"test_{uuid4().hex}"
                    ).normalize(snapshot)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
