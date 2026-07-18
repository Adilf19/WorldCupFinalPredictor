"""Expected-lineup and positional matchup prediction."""

from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupPrediction, PredictedLineup
from matchup_engine.lineup_predictor import LineupPredictor
from matchup_engine.pipeline import MatchupPredictionPipeline
from matchup_engine.positional_matchup import PositionalMatchupPredictor
from matchup_engine.spatial_matchup import SpatialMatchupPredictor

__all__ = [
    "LineupPredictor",
    "MatchupPrediction",
    "MatchupPredictionPipeline",
    "PositionalMatchupPredictor",
    "SpatialMatchupPredictor",
    "PredictedLineup",
    "PredictorConfig",
]
