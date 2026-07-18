"""Ingest all available World Cup match results without downloading event files."""

import argparse
import asyncio
import json
from dataclasses import asdict

from data_collection.ingestion import ingest_provider
from data_collection.providers import StatsBombOpenDataProvider
from database.connection import session_scope

WORLD_CUP_SEASONS = (106, 3, 55, 54, 51, 272, 270, 269)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", type=int, default=43)
    parser.add_argument("--season-ids", type=int, nargs="+", default=WORLD_CUP_SEASONS)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    summaries = []
    for season_id in args.season_ids:
        provider = StatsBombOpenDataProvider(
            competition_id=args.competition_id,
            season_id=season_id,
            team_names=(),
            include_event_data=False,
        )
        with session_scope() as session:
            report = await ingest_provider(provider, session=session)
        summaries.append(asdict(report))
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
