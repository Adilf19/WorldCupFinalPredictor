"""Add provider reference tables.

Revision ID: 20260718_01
Revises: None
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260718_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_reference_table(
    table_name: str,
    entity_table: str,
    entity_column: str,
    external_constraint: str,
    entity_constraint: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column(
            entity_column,
            sa.Integer(),
            sa.ForeignKey(f"{entity_table}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "external_id", name=external_constraint),
        sa.UniqueConstraint("provider", entity_column, name=entity_constraint),
    )
    op.create_index(
        f"ix_{table_name}_{entity_column}", table_name, [entity_column]
    )


def upgrade() -> None:
    _create_reference_table(
        "competition_provider_references",
        "competitions",
        "competition_id",
        "uq_competition_provider_external",
        "uq_competition_provider_entity",
    )
    _create_reference_table(
        "team_provider_references",
        "teams",
        "team_id",
        "uq_team_provider_external",
        "uq_team_provider_entity",
    )
    _create_reference_table(
        "player_provider_references",
        "players",
        "player_id",
        "uq_player_provider_external",
        "uq_player_provider_entity",
    )
    _create_reference_table(
        "match_provider_references",
        "matches",
        "match_id",
        "uq_match_provider_external",
        "uq_match_provider_entity",
    )


def downgrade() -> None:
    op.drop_table("match_provider_references")
    op.drop_table("player_provider_references")
    op.drop_table("team_provider_references")
    op.drop_table("competition_provider_references")
