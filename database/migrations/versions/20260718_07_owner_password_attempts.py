"""Add rolling-window owner password login attempts.

Revision ID: 20260718_07
Revises: 20260718_06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_07"
down_revision: str | None = "20260718_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_ip", sa.String(length=64), nullable=False),
        sa.Column("succeeded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_owner_attempt_ip_created",
        "owner_login_attempts",
        ["request_ip", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_owner_attempt_ip_created", table_name="owner_login_attempts")
    op.drop_table("owner_login_attempts")
