"""Regression tests for model contracts and Monte Carlo simulation."""

import unittest

from pydantic import ValidationError

from simulation.contracts import MonteCarloResult
from simulation.monte_carlo import MonteCarloSimulator


class MonteCarloSimulatorTests(unittest.TestCase):
    def test_seeded_simulation_is_reproducible_and_normalized(self) -> None:
        simulator = MonteCarloSimulator(simulations=20_000, random_seed=42)
        first = simulator.simulate(expected_goals_home=1.6, expected_goals_away=1.0)
        second = simulator.simulate(expected_goals_home=1.6, expected_goals_away=1.0)
        self.assertEqual(first, second)
        self.assertAlmostEqual(
            first.home_win_probability + first.draw_probability + first.away_win_probability,
            1.0,
        )
        self.assertGreater(first.home_win_probability, first.away_win_probability)
        self.assertEqual(sum(item.occurrences for item in first.scorelines), 20_000)

    def test_negative_goal_rate_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MonteCarloSimulator(simulations=10).simulate(
                expected_goals_home=-0.1, expected_goals_away=1.0
            )

    def test_contract_rejects_probabilities_that_do_not_sum_to_one(self) -> None:
        with self.assertRaises(ValidationError):
            MonteCarloResult(
                simulations=10,
                random_seed=1,
                expected_goals_home=1,
                expected_goals_away=1,
                home_win_probability=0.4,
                draw_probability=0.4,
                away_win_probability=0.4,
                mean_home_goals=1,
                mean_away_goals=1,
                home_goals_interval_90=(0, 3),
                away_goals_interval_90=(0, 3),
                scorelines=(),
            )


if __name__ == "__main__":
    unittest.main()
