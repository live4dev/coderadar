"""Add scan cancellation support

Revision ID: 008
Revises: 007
Create Date: 2026-03-18 00:00:00.000000

Adds cancel_requested boolean column to scans table and adds 'cancelled'
to the scanstatus enum. SQLite stores enums as VARCHAR so no column alter
is needed there; PostgreSQL requires ALTER TYPE.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cancel_requested boolean column (default False)
    op.add_column("scans", sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="0"))

    # For PostgreSQL: add 'cancelled' to the scanstatus enum type
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("ALTER TYPE scanstatus ADD VALUE IF NOT EXISTS 'cancelled'"))


def downgrade() -> None:
    op.drop_column("scans", "cancel_requested")
    # Note: removing an enum value from PostgreSQL is not supported without recreating the type.
