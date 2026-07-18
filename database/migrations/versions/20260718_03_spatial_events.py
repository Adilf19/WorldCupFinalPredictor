"""Store normalized player action coordinates.

Revision ID: 20260718_03
Revises: 20260718_02
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_03"
down_revision: str | Sequence[str] | None = "20260718_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spatial_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("second", sa.Float(), nullable=False, server_default="0"),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("end_x", sa.Float()),
        sa.Column("end_y", sa.Float()),
        sa.Column("outcome", sa.String(50)),
        sa.Column("under_pressure", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("provider", "external_id", name="uq_spatial_provider_external"),
        sa.CheckConstraint("x >= 0 AND x <= 1 AND y >= 0 AND y <= 1", name="ck_spatial_start_unit_pitch"),
        sa.CheckConstraint("(end_x IS NULL OR (end_x >= 0 AND end_x <= 1)) AND (end_y IS NULL OR (end_y >= 0 AND end_y <= 1))", name="ck_spatial_end_unit_pitch"),
    )
    op.create_index("idx_spatial_player", "spatial_events", ["player_id"])
    op.create_index("idx_spatial_match", "spatial_events", ["match_id"])


def downgrade() -> None:
    op.drop_table("spatial_events")
