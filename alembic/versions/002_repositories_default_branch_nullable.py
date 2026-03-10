"""repositories default_branch nullable

Revision ID: 002
Revises: 001
Create Date: 2026-03-10

"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("repositories") as batch_op:
            batch_op.alter_column(
                "default_branch",
                existing_type=sa.String(255),
                nullable=True,
                server_default=None,
            )
    else:
        op.alter_column(
            "repositories",
            "default_branch",
            existing_type=sa.String(255),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("repositories") as batch_op:
            batch_op.alter_column(
                "default_branch",
                existing_type=sa.String(255),
                nullable=False,
                server_default="main",
            )
    else:
        op.alter_column(
            "repositories",
            "default_branch",
            existing_type=sa.String(255),
            nullable=False,
            server_default="main",
        )
