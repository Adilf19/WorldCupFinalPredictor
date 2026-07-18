"""Unit tests for API-Football response normalization."""

import unittest

from data_collection.api_football import (
    ApiFootballLiveProvider,
    coach_photo_url,
    player_photo_url,
)


class FakeClient:
    def fixture_lineups(self, fixture_id: str):
        return [
            {"startXI": [{"player": {"id": i, "name": f"Home {i}", "number": i}} for i in range(1, 12)]},
            {"startXI": [{"player": {"id": i + 20, "name": f"Away {i}", "number": i}} for i in range(1, 12)]},
        ]

    def fixture(self, fixture_id: str):
        return {
            "fixture": {"status": {"short": "2H", "elapsed": 67}},
            "goals": {"home": 2, "away": 1},
        }

    def fixture_events(self, fixture_id: str):
        return [{
            "time": {"elapsed": 64, "extra": None},
            "team": {"name": "Home"},
            "player": {"name": "Home 9"},
            "type": "Goal",
            "detail": "Normal Goal",
            "comments": None,
        }]


class ApiFootballNormalizationTests(unittest.TestCase):
    def test_documented_media_urls_are_stable(self) -> None:
        self.assertEqual(player_photo_url(278), "https://media.api-sports.io/football/players/278.png")
        self.assertEqual(coach_photo_url(40), "https://media.api-sports.io/football/coachs/40.png")

    def test_confirmed_lineups_include_free_media_urls(self) -> None:
        lineups = ApiFootballLiveProvider(FakeClient()).confirmed_lineups("123")
        self.assertIsNotNone(lineups)
        self.assertEqual(len(lineups[0]), 11)
        self.assertEqual(lineups[0][0]["photo_url"], player_photo_url(1))

    def test_live_fixture_and_event_are_normalized(self) -> None:
        live = ApiFootballLiveProvider(FakeClient()).live("123", scheduled_status="scheduled")
        self.assertEqual(live["status"], "2h")
        self.assertEqual(live["minute"], 67)
        self.assertEqual(live["home_score"], 2)
        self.assertEqual(live["events"][0]["player"], "Home 9")


if __name__ == "__main__":
    unittest.main()
