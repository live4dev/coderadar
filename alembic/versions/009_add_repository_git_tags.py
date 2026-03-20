"""Add repository_git_tags table

Revision ID: 009
Revises: 008
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repository_git_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sha", sa.String(40), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("tagger_name", sa.String(255), nullable=True),
        sa.Column("tagger_email", sa.String(255), nullable=True),
        sa.Column("tagged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "name", name="uq_repository_git_tags_repository_id_name"),
    )
    op.create_index("ix_repository_git_tags_repository_id", "repository_git_tags", ["repository_id"])


def downgrade() -> None:
    op.drop_index("ix_repository_git_tags_repository_id", table_name="repository_git_tags")
    op.drop_table("repository_git_tags")
