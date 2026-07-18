"""Attach licensed Sportradar player/headshot and team-logo manifests."""

import argparse
from dataclasses import asdict
from datetime import date

from api.config import settings
from data_collection.sportradar_media import SportradarMediaClient, SportradarMediaSynchronizer
from database.connection import session_scope


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()
    client = SportradarMediaClient(
        api_key=settings.sportradar_api_key or "",
        access_level=settings.sportradar_access_level,
        provider=settings.sportradar_image_provider,
        league=settings.sportradar_image_league,
    )
    with session_scope() as session:
        report = SportradarMediaSynchronizer(session, client).sync(year=args.year)
    print(asdict(report))


if __name__ == "__main__":
    main()
