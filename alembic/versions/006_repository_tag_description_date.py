"""Add description and created_at to repository_tags

Revision ID: 006
Revises: 005
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repository_tags", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "repository_tags",
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("repository_tags", "created_at")
    op.drop_column("repository_tags", "description")
