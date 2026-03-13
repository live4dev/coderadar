"""Add project_tags, repository_tags, developer_tags

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop if exist (recovery from partial run where tables were created without unique constraints)
    conn = op.get_bind()
    for table in ("developer_tags", "repository_tags", "project_tags"):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))

    op.create_table(
        "project_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("project_id", "tag", name="uq_project_tags_project_id_tag"),
    )
    op.create_index("ix_project_tags_project_id", "project_tags", ["project_id"])

    op.create_table(
        "repository_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("repository_id", "tag", name="uq_repository_tags_repository_id_tag"),
    )
    op.create_index("ix_repository_tags_repository_id", "repository_tags", ["repository_id"])

    op.create_table(
        "developer_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("developer_id", sa.Integer(), sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("developer_id", "tag", name="uq_developer_tags_developer_id_tag"),
    )
    op.create_index("ix_developer_tags_developer_id", "developer_tags", ["developer_id"])


def downgrade() -> None:
    op.drop_table("developer_tags")
    op.drop_table("repository_tags")
    op.drop_table("project_tags")
