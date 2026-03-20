"""Add developer_daily_activity table

Revision ID: 010
Revises: 009
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "developer_daily_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("commit_date", sa.Date(), nullable=False),
        sa.Column("commit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["profile_id"], ["developer_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "commit_date", name="uq_developer_daily_activity_profile_date"),
    )
    op.create_index("ix_developer_daily_activity_profile_id", "developer_daily_activity", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_developer_daily_activity_profile_id", table_name="developer_daily_activity")
    op.drop_table("developer_daily_activity")
