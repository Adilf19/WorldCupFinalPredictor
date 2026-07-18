"""Ingest two years of CC0 national-team results."""

import argparse
import asyncio
from datetime import date

from data_collection.ingestion import ingest_provider
from data_collection.providers.international_results import InternationalResultsProvider
from database.connection import session_scope


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", nargs="+", default=["Spain", "Argentina"])
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 7, 19))
    parser.add_argument("--days", type=int, default=730)
    args = parser.parse_args()
    provider = InternationalResultsProvider(team_names=tuple(args.teams), as_of=args.as_of, lookback_days=args.days)
    with session_scope() as session:
        report = asyncio.run(ingest_provider(provider, session=session))
        print(f"provider={report.provider} created={report.total_created} updated={report.total_updated}")


if __name__ == "__main__":
    main()
