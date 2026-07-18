"""Select the verified France–England 2026 World Cup bronze final."""

from datetime import datetime, timezone

from sqlalchemy import select

from api.schemas import SelectFixtureBody
from api.services import SelectedFixtureService
from database.connection import session_scope
from database.models import Match, Team
from scripts.seed_bronze_final_lineups import seed_possible_lineups


def main() -> None:
    kickoff = datetime(2026, 7, 18, 21, 0, tzinfo=timezone.utc)  # 22:00 BST
    with session_scope() as session:
        seed_possible_lineups(session)
        france = session.scalar(select(Team).where(Team.name == "France"))
        england = session.scalar(select(Team).where(Team.name == "England"))
        if france is None or england is None:
            raise RuntimeError("France and England must be ingested before selecting the fixture")
        match = session.scalar(
            select(Match).where(
                Match.home_team == france.id,
                Match.away_team == england.id,
                Match.date == kickoff.date(),
            )
        )
        fixture = SelectedFixtureService(session).select(
            SelectFixtureBody(
                provider="fifa_official",
                external_id="fifa-world-cup-2026-match-103-bronze-final",
                home_name="France",
                away_name="England",
                kickoff_at=kickoff,
                match_id=match.id if match else None,
                home_team_id=france.id,
                away_team_id=england.id,
                timing_accuracy="exact",
                competition_name="FIFA World Cup 2026 · Third-place match",
                competition_format="knockout",
            ),
            owner_email="system:fifa_official",
        )
    print(fixture.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
