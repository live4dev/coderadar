"""Add license and is_direct fields to dependencies

Revision ID: 012
Revises: 011
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dependencies", sa.Column("license_spdx", sa.String(128), nullable=True))
    op.add_column("dependencies", sa.Column("license_raw", sa.String(256), nullable=True))
    op.add_column(
        "dependencies",
        sa.Column("license_risk", sa.String(16), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "dependencies",
        sa.Column("is_direct", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("dependencies", "is_direct")
    op.drop_column("dependencies", "license_risk")
    op.drop_column("dependencies", "license_raw")
    op.drop_column("dependencies", "license_spdx")
