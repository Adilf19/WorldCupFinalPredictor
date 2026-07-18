"""Add provider-backed player photos.

Revision ID: 20260718_06
Revises: 20260718_05
Create Date: 2026-07-18
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260718_06"
down_revision: str | Sequence[str] | None = "20260718_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("photo_url", sa.String(500)))


def downgrade() -> None:
    op.drop_column("players", "photo_url")
