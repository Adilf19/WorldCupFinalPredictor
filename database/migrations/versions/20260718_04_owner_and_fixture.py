"""Add owner verification and selected fixture state.

Revision ID: 20260718_04
Revises: 20260718_03
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_04"
down_revision: str | Sequence[str] | None = "20260718_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_login_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("salt", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("request_ip", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index("idx_owner_challenge_email_created", "owner_login_challenges", ["email", "created_at"])
    op.create_table(
        "owner_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("token_hash", name="uq_owner_sessions_token_hash"),
    )
    op.create_table(
        "selected_fixtures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("home_name", sa.String(100), nullable=False),
        sa.Column("away_name", sa.String(100), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("teams.id")),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("teams.id")),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("provider", "external_id", name="uq_selected_fixture_provider_external"),
    )
    op.create_index("idx_selected_fixture_active", "selected_fixtures", ["is_active"])


def downgrade() -> None:
    op.drop_table("selected_fixtures")
    op.drop_table("owner_sessions")
    op.drop_table("owner_login_challenges")
