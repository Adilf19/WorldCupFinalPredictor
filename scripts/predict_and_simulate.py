"""Predict goal rates and simulate the Spain–Argentina final."""

import argparse
import json
from datetime import date

from sqlalchemy import select

from database.connection import session_scope
from database.crud import TeamRepository
from database.lookups import unique_team_by_name
from database.models import Match
from simulation.pipeline import PredictionSimulationPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default="Spain")
    parser.add_argument("--away", default="Argentina")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 7, 19))
    parser.add_argument("--simulations", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--no-persist", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with session_scope() as session:
        teams = TeamRepository(session)
        home = unique_team_by_name(teams, args.home)
        away = unique_team_by_name(teams, args.away)
        match_id = None
        if not args.no_persist:
            match_id = session.scalar(
                select(Match.id).where(
                    Match.home_team == home.id,
                    Match.away_team == away.id,
                    Match.date == args.as_of,
                )
            )
        goals, result = PredictionSimulationPipeline(session).run(
            home_team_id=home.id,
            away_team_id=away.id,
            as_of=args.as_of,
            simulations=args.simulations,
            random_seed=args.seed,
            match_id=match_id,
        )
    output = {
        "prediction": goals.model_dump(mode="json"),
        "simulation": result.model_dump(mode="json", exclude={"scorelines"}),
        "most_likely_scorelines": [
            scoreline.model_dump(mode="json") for scoreline in result.scorelines[:10]
        ],
        "persisted_match_id": match_id,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
