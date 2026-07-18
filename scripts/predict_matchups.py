"""Predict expected lineups and positional battles for two teams."""

import argparse
from datetime import date

from database import session_scope
from database.crud import TeamRepository
from database.lookups import unique_team_by_name
from matchup_engine import MatchupPredictionPipeline, PredictorConfig


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default="Spain", help="Canonical home team name")
    parser.add_argument("--away", default="Argentina", help="Canonical away team name")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date(2026, 7, 19),
        help="Exclusive evidence cutoff in YYYY-MM-DD format",
    )
    parser.add_argument("--lineup-lookback", type=int, default=12)
    parser.add_argument("--half-life-days", type=float, default=120.0)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    config = PredictorConfig(
        lineup_lookback_matches=args.lineup_lookback,
        recency_half_life_days=args.half_life_days,
    )
    with session_scope() as session:
        teams = TeamRepository(session)
        prediction = MatchupPredictionPipeline(session, config=config).predict(
            home_team_id=unique_team_by_name(teams, args.home).id,
            away_team_id=unique_team_by_name(teams, args.away).id,
            as_of=args.as_of,
        )
    print(prediction.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
