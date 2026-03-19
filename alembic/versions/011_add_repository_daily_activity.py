"""Add repository_daily_activity table

Revision ID: 011
Revises: 010
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repository_daily_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("commit_date", sa.Date(), nullable=False),
        sa.Column("commit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "commit_date", name="uq_repository_daily_activity_repository_date"),
    )
    op.create_index("ix_repository_daily_activity_repository_id", "repository_daily_activity", ["repository_id"])


def downgrade() -> None:
    op.drop_index("ix_repository_daily_activity_repository_id", table_name="repository_daily_activity")
    op.drop_table("repository_daily_activity")
