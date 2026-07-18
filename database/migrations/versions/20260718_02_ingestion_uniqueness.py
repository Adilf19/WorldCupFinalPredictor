"""Enforce ingestion record uniqueness.

Revision ID: 20260718_02
Revises: 20260718_01
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_02"
down_revision: str | Sequence[str] | None = "20260718_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_lineup_match_player", "lineups", ["match_id", "player_id"]
    )
    op.create_unique_constraint(
        "uq_player_stats_match_player",
        "player_match_stats",
        ["match_id", "player_id"],
    )
    op.create_unique_constraint(
        "uq_matchup_match_attacker_defender",
        "matchup_events",
        ["match_id", "attacker_id", "defender_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_matchup_match_attacker_defender", "matchup_events", type_="unique"
    )
    op.drop_constraint(
        "uq_player_stats_match_player", "player_match_stats", type_="unique"
    )
    op.drop_constraint("uq_lineup_match_player", "lineups", type_="unique")
