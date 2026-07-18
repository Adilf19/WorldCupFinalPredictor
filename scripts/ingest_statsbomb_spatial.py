"""Ingest official open event locations for Spain and Argentina."""

import argparse
import asyncio
import json
from dataclasses import asdict

from data_collection.ingestion import ingest_provider
from data_collection.providers import StatsBombOpenDataProvider
from database.connection import session_scope


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition-id", type=int, default=43)
    parser.add_argument("--season-id", type=int, default=106)
    parser.add_argument("--teams", nargs="+", default=["Spain", "Argentina"])
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    provider = StatsBombOpenDataProvider(
        competition_id=args.competition_id,
        season_id=args.season_id,
        team_names=tuple(args.teams),
    )
    with session_scope() as session:
        report = await ingest_provider(provider, session=session)
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    asyncio.run(run())
