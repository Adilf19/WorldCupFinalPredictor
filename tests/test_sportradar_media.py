"""Pure unit tests for licensed media parsing and keeper scoring."""

import unittest

from data_collection.sportradar_media import normalized_name, parse_manifest_assets
from matchup_engine.goalkeeper_comparison import GoalkeeperComparisonEngine, GoalkeeperProfile


class SportradarManifestTests(unittest.TestCase):
    def test_nested_manifest_prefers_small_display_asset(self) -> None:
        payload = {"assetlist": {"assets": [{
            "id": "asset-1",
            "title": "Mbappé, Kylian",
            "copyright": "Licensed Provider",
            "links": [
                {"href": "/headshots/players/asset-1/original.jpg", "width": 1800},
                {"href": "/headshots/players/asset-1/250w-resize.jpg", "width": 250},
            ],
            "refs": [{"name": "Kylian Mbappé", "type": "profile"}],
        }]}}
        assets = parse_manifest_assets(payload)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].href, "/headshots/players/asset-1/250w-resize.jpg")
        self.assertIn("Kylian Mbappé", assets[0].names)

    def test_entity_names_are_conservatively_normalized(self) -> None:
        self.assertEqual(normalized_name("Mbappé, Kylian"), "kylian mbappe")
        self.assertEqual(normalized_name("Liverpool FC"), "liverpool")


class GoalkeeperScoreTests(unittest.TestCase):
    def test_lower_concession_and_higher_prevention_favour_home_keeper(self) -> None:
        home = GoalkeeperProfile(10, 900, 0.7, 0.5, 0.25, 7.4)
        away = GoalkeeperProfile(10, 900, 1.4, 0.2, -0.15, 6.7)
        score, dimensions = GoalkeeperComparisonEngine._score(home, away)
        self.assertGreater(float(score), 0)
        self.assertEqual(len(dimensions), 4)

    def test_missing_keeper_data_is_unscored(self) -> None:
        empty = GoalkeeperProfile(0, 0, None, None, None, None)
        score, dimensions = GoalkeeperComparisonEngine._score(empty, empty)
        self.assertIsNone(score)
        self.assertEqual(dimensions, [])


if __name__ == "__main__":
    unittest.main()
