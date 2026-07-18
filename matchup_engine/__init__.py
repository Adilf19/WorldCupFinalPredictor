"""Expected-lineup and positional matchup prediction."""

from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupPrediction, PredictedLineup
from matchup_engine.lineup_predictor import LineupPredictor
from matchup_engine.h2h_engine import DirectH2HEngine
from matchup_engine.pipeline import MatchupPredictionPipeline
from matchup_engine.positional_matchup import PositionalMatchupPredictor
from matchup_engine.spatial_matchup import SpatialMatchupPredictor
from matchup_engine.similarity_engine import PlayerSimilarityEngine

__all__ = [
    "LineupPredictor",
    "DirectH2HEngine",
    "MatchupPrediction",
    "MatchupPredictionPipeline",
    "PositionalMatchupPredictor",
    "SpatialMatchupPredictor",
    "PlayerSimilarityEngine",
    "PredictedLineup",
    "PredictorConfig",
]
