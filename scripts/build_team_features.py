"""Build and print a leakage-safe feature comparison for two teams."""

import argparse
from datetime import date

from database import session_scope
from database.crud import TeamRepository
from feature_engineering import MatchFeaturePipeline, TeamFeatureConfig


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default="Spain", help="Canonical home team name")
    parser.add_argument("--away", default="Argentina", help="Canonical away team name")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date(2026, 7, 19),
        help="Exclusive history cutoff in YYYY-MM-DD format",
    )
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--half-life-days", type=float, default=180.0)
    return parser.parse_args()


def _team_id(repository: TeamRepository, name: str) -> int:
    matches = repository.list(limit=2, name=name)
    if not matches:
        raise LookupError(f"Team {name!r} was not found")
    if len(matches) > 1:
        raise LookupError(f"Team name {name!r} is ambiguous")
    return matches[0].id


def main() -> None:
    args = _arguments()
    config = TeamFeatureConfig(
        lookback_matches=args.lookback,
        recency_half_life_days=args.half_life_days,
    )
    with session_scope() as session:
        teams = TeamRepository(session)
        comparison = MatchFeaturePipeline(session, config=config).build(
            home_team_id=_team_id(teams, args.home),
            away_team_id=_team_id(teams, args.away),
            as_of=args.as_of,
        )
    print(comparison.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
