"""Validated Monte Carlo simulation outputs."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SimulationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScorelineProbability(SimulationContract):
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    occurrences: int = Field(ge=0)
    probability: float = Field(ge=0, le=1)


class MonteCarloResult(SimulationContract):
    simulation_version: str = "independent_poisson_mc_v1"
    simulations: int = Field(ge=1)
    random_seed: int
    expected_goals_home: float = Field(ge=0)
    expected_goals_away: float = Field(ge=0)
    home_win_probability: float = Field(ge=0, le=1)
    draw_probability: float = Field(ge=0, le=1)
    away_win_probability: float = Field(ge=0, le=1)
    mean_home_goals: float = Field(ge=0)
    mean_away_goals: float = Field(ge=0)
    home_goals_interval_90: tuple[int, int]
    away_goals_interval_90: tuple[int, int]
    scorelines: tuple[ScorelineProbability, ...]

    @model_validator(mode="after")
    def validate_outcomes(self) -> "MonteCarloResult":
        total = self.home_win_probability + self.draw_probability + self.away_win_probability
        if abs(total - 1.0) > 1e-9:
            raise ValueError("outcome probabilities must sum to one")
        return self
