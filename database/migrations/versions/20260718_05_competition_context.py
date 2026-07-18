"""Add club/country context and competition format metadata.

Revision ID: 20260718_05
Revises: 20260718_04
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_05"
down_revision: str | Sequence[str] | None = "20260718_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("team_type", sa.String(20), nullable=False, server_default="club"))
    op.add_column("competitions", sa.Column("format", sa.String(20), nullable=False, server_default="league"))
    op.add_column("competitions", sa.Column("team_type", sa.String(20), nullable=False, server_default="club"))
    op.add_column("matches", sa.Column("stage", sa.String(50)))
    op.add_column("matches", sa.Column("is_knockout", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("selected_fixtures", sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id")))
    op.add_column("selected_fixtures", sa.Column("competition_name", sa.String(100)))
    op.add_column("selected_fixtures", sa.Column("competition_format", sa.String(20), nullable=False, server_default="league"))
    op.execute("UPDATE teams SET team_type = 'country' WHERE id IN (SELECT DISTINCT home_team FROM matches JOIN competitions ON competitions.id = matches.competition_id WHERE competitions.country = 'International') OR id IN (SELECT DISTINCT away_team FROM matches JOIN competitions ON competitions.id = matches.competition_id WHERE competitions.country = 'International')")
    op.execute("UPDATE competitions SET team_type = 'country', format = 'hybrid' WHERE country = 'International' OR name ILIKE '%World Cup%'")
    op.execute("UPDATE matches SET stage = 'FINAL', is_knockout = true WHERE date = '2026-07-19'")
    op.execute("UPDATE selected_fixtures SET competition_name = 'FIFA World Cup 2026', competition_format = 'knockout' WHERE home_name = 'Spain' AND away_name = 'Argentina'")
    op.create_index("idx_teams_team_type", "teams", ["team_type"])
    op.create_index("idx_matches_competition_date", "matches", ["competition_id", "date"])


def downgrade() -> None:
    op.drop_index("idx_matches_competition_date", table_name="matches")
    op.drop_index("idx_teams_team_type", table_name="teams")
    op.drop_column("selected_fixtures", "competition_format")
    op.drop_column("selected_fixtures", "competition_name")
    op.drop_column("selected_fixtures", "competition_id")
    op.drop_column("matches", "is_knockout")
    op.drop_column("matches", "stage")
    op.drop_column("competitions", "team_type")
    op.drop_column("competitions", "format")
    op.drop_column("teams", "team_type")
