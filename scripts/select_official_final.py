"""Select the verified FIFA 2026 final as the initial active dashboard fixture."""

from datetime import datetime, timezone

from sqlalchemy import select

from api.schemas import SelectFixtureBody
from api.services import SelectedFixtureService
from database.connection import session_scope
from database.models import Match, Team


def main() -> None:
    with session_scope() as session:
        spain = session.scalar(select(Team).where(Team.name == "Spain"))
        argentina = session.scalar(select(Team).where(Team.name == "Argentina"))
        if spain is None or argentina is None:
            raise RuntimeError("Spain and Argentina must be seeded first")
        match = session.scalar(
            select(Match).where(
                Match.home_team == spain.id,
                Match.away_team == argentina.id,
                Match.date == datetime(2026, 7, 19).date(),
            )
        )
        fixture = SelectedFixtureService(session).select(
            SelectFixtureBody(
                provider="fifa_official",
                external_id="fifa-world-cup-2026-final",
                home_name="Spain",
                away_name="Argentina",
                kickoff_at=datetime(2026, 7, 19, 19, 0, tzinfo=timezone.utc),
                match_id=match.id if match else None,
                home_team_id=spain.id,
                away_team_id=argentina.id,
                timing_accuracy="exact",
            ),
            owner_email="system:fifa_official",
        )
    print(fixture.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
