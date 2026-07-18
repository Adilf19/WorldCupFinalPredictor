"""Add licensed team and manager media URLs.

Revision ID: 20260718_08
Revises: 20260718_07
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_08"
down_revision: str | Sequence[str] | None = "20260718_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("logo_url", sa.String(500)))
    op.add_column("managers", sa.Column("photo_url", sa.String(500)))


def downgrade() -> None:
    op.drop_column("managers", "photo_url")
    op.drop_column("teams", "logo_url")
