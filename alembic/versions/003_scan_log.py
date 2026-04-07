"""Add scan_log column to scans table

Revision ID: 003
Revises: 002
Create Date: 2026-04-03 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("scan_log", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "scan_log")
