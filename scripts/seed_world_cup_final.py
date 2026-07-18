"""Seed Spain, Argentina, their squads, and the 2026 World Cup final."""

from database import session_scope
from database.seeding import WorldCupFinalSeeder


def main() -> None:
    """Run the seed in one atomic transaction and print a concise summary."""
    with session_scope() as session:
        summary = WorldCupFinalSeeder(session).seed()

    print("2026 World Cup final seed completed")
    print(f"  competitions created: {summary.competitions_created}")
    print(f"  teams created:        {summary.teams_created}")
    print(f"  managers created:     {summary.managers_created}")
    print(f"  players created:      {summary.players_created}")
    print(f"  memberships created:  {summary.memberships_created}")
    print(f"  matches created:      {summary.matches_created}")
    print(f"  total rows created:   {summary.total_created}")


if __name__ == "__main__":
    main()
