"""Sync API-Football media for the currently selected fixture."""

from dataclasses import asdict
import json

from sqlalchemy.orm import Session

from api.config import settings
from api.services import SelectedFixtureService
from data_collection.api_football import ApiFootballClient, ApiFootballSynchronizer
from database.connection import engine
from database.models import Team


def main() -> None:
    client = ApiFootballClient(
        api_key=settings.api_football_api_key or "",
        base_url=settings.api_football_base_url,
    )
    with Session(engine) as session, session.begin():
        fixture = SelectedFixtureService(session).active_model()
        if fixture is None or fixture.home_team_id is None or fixture.away_team_id is None:
            raise SystemExit("Select a canonical fixture before running this command")
        teams = [session.get(Team, fixture.home_team_id), session.get(Team, fixture.away_team_id)]
        if any(team is None for team in teams):
            raise SystemExit("The selected fixture does not have canonical teams")
        report = ApiFootballSynchronizer(session, client).sync_teams(teams)
        print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
