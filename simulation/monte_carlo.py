"""Deterministic-seed Monte Carlo scoreline simulation."""

from collections import Counter

import numpy as np

from simulation.contracts import MonteCarloResult, ScorelineProbability


class MonteCarloSimulator:
    """Simulate independent Poisson scores from learned expected-goal rates."""

    def __init__(self, *, simulations: int = 100_000, random_seed: int = 20260719) -> None:
        if simulations < 1:
            raise ValueError("simulations must be positive")
        self.simulations = simulations
        self.random_seed = random_seed

    def simulate(
        self, *, expected_goals_home: float, expected_goals_away: float
    ) -> MonteCarloResult:
        if expected_goals_home < 0 or expected_goals_away < 0:
            raise ValueError("expected goals cannot be negative")
        generator = np.random.default_rng(self.random_seed)
        home = generator.poisson(expected_goals_home, self.simulations)
        away = generator.poisson(expected_goals_away, self.simulations)
        home_wins = int(np.sum(home > away))
        draws = int(np.sum(home == away))
        away_wins = self.simulations - home_wins - draws
        counts = Counter(zip(home.tolist(), away.tolist()))
        scorelines = tuple(
            ScorelineProbability(
                home_goals=int(score[0]),
                away_goals=int(score[1]),
                occurrences=occurrences,
                probability=occurrences / self.simulations,
            )
            for score, occurrences in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )
        )
        return MonteCarloResult(
            simulations=self.simulations,
            random_seed=self.random_seed,
            expected_goals_home=expected_goals_home,
            expected_goals_away=expected_goals_away,
            home_win_probability=home_wins / self.simulations,
            draw_probability=draws / self.simulations,
            away_win_probability=away_wins / self.simulations,
            mean_home_goals=float(np.mean(home)),
            mean_away_goals=float(np.mean(away)),
            home_goals_interval_90=(int(np.quantile(home, 0.05)), int(np.quantile(home, 0.95))),
            away_goals_interval_90=(int(np.quantile(away, 0.05)), int(np.quantile(away, 0.95))),
            scorelines=scorelines,
        )
