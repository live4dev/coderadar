"""Add tech_radar_overrides table

Revision ID: 004
Revises: 003
Create Date: 2026-05-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tech_radar_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tech_name", sa.String(255), nullable=False),
        sa.Column("quadrant", sa.String(64), nullable=False),
        sa.Column("ring", sa.String(32), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tech_radar_overrides_tech_name", "tech_radar_overrides", ["tech_name"])
    op.create_index("ix_tech_radar_overrides_project_id", "tech_radar_overrides", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_tech_radar_overrides_project_id", "tech_radar_overrides")
    op.drop_index("ix_tech_radar_overrides_tech_name", "tech_radar_overrides")
    op.drop_table("tech_radar_overrides")
