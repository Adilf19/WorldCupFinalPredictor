"""Seed FIFA's published possible XIs for the 2026 bronze final."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import session_scope
from database.models import Player, Team, TeamPlayer

SQUAD_START = date(2026, 6, 1)
SQUAD_END = date(2026, 7, 19)

POSSIBLE_XIS = {
    "France": (
        ("Mike Maignan", "GK"),
        ("Malo Gusto", "DF"),
        ("Maxence Lacroix", "DF"),
        ("Ibrahima Konaté", "DF"),
        ("Theo Hernández", "DF"),
        ("Warren Zaïre-Emery", "MF"),
        ("N'Golo Kanté", "MF"),
        ("Michael Olise", "FW"),
        ("Rayan Cherki", "FW"),
        ("Désiré Doué", "FW"),
        ("Kylian Mbappé", "FW"),
    ),
    "England": (
        ("Dean Henderson", "GK"),
        ("Trevoh Chalobah", "DF"),
        ("Marc Guéhi", "DF"),
        ("John Stones", "DF"),
        ("Djed Spence", "DF"),
        ("Kobbie Mainoo", "MF"),
        ("Elliot Anderson", "MF"),
        ("Morgan Rogers", "MF"),
        ("Noni Madueke", "FW"),
        ("Harry Kane", "FW"),
        ("Marcus Rashford", "FW"),
    ),
}


def seed_possible_lineups(session: Session) -> None:
    for team_name, possible_xi in POSSIBLE_XIS.items():
        team = session.scalar(select(Team).where(Team.name == team_name))
        if team is None:
            raise RuntimeError(f"{team_name} must be ingested before seeding its possible XI")

        # Close legacy provider memberships that had no historical bounds.
        legacy = session.scalars(
            select(TeamPlayer).where(
                TeamPlayer.team_id == team.id,
                TeamPlayer.start_date.is_(None),
                TeamPlayer.end_date.is_(None),
            )
        ).all()
        for membership in legacy:
            membership.end_date = date(2022, 12, 31)

        for player_name, position in possible_xi:
            player = session.scalar(select(Player).where(Player.name == player_name))
            if player is None:
                player = Player(
                    name=player_name,
                    nationality=team_name,
                    primary_position=position,
                )
                session.add(player)
                session.flush()
            membership = session.scalar(
                select(TeamPlayer).where(
                    TeamPlayer.team_id == team.id,
                    TeamPlayer.player_id == player.id,
                    TeamPlayer.start_date == SQUAD_START,
                )
            )
            if membership is None:
                session.add(
                    TeamPlayer(
                        team_id=team.id,
                        player_id=player.id,
                        start_date=SQUAD_START,
                        end_date=SQUAD_END,
                    )
                )
    session.flush()


def main() -> None:
    with session_scope() as session:
        seed_possible_lineups(session)
    print("France and England possible XIs seeded from FIFA's match preview")


if __name__ == "__main__":
    main()
