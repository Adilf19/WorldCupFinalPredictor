"""Add provider-neutral player availability reports.

Revision ID: 20260718_09
Revises: 20260718_08
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_09"
down_revision: str | Sequence[str] | None = "20260718_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(255)),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_return", sa.Date()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("provider", "external_id", name="uq_availability_provider_external"),
        sa.CheckConstraint(
            "status IN ('available','doubtful','out','suspended','unknown')",
            name="ck_player_availability_status",
        ),
    )
    op.create_index("idx_availability_player_reported", "player_availability", ["player_id", "reported_at"])


def downgrade() -> None:
    op.drop_index("idx_availability_player_reported", table_name="player_availability")
    op.drop_table("player_availability")
