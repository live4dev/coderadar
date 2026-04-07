"""Extend dependency table with richer license metadata

Revision ID: 002
Revises: 001
Create Date: 2026-04-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dependencies", sa.Column("license_expression", sa.Text(), nullable=True))
    op.add_column("dependencies", sa.Column("license_confidence", sa.String(16), nullable=False, server_default="unknown"))
    op.add_column("dependencies", sa.Column("license_source", sa.String(64), nullable=True))
    op.add_column("dependencies", sa.Column("license_notes", sa.Text(), nullable=True))
    op.add_column("dependencies", sa.Column("discovery_mode", sa.String(32), nullable=False, server_default="unknown"))
    op.add_column("dependencies", sa.Column("is_optional_dependency", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("dependencies", sa.Column("is_private", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("dependencies", sa.Column("package_manager", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("dependencies", "package_manager")
    op.drop_column("dependencies", "is_private")
    op.drop_column("dependencies", "is_optional_dependency")
    op.drop_column("dependencies", "discovery_mode")
    op.drop_column("dependencies", "license_notes")
    op.drop_column("dependencies", "license_source")
    op.drop_column("dependencies", "license_confidence")
    op.drop_column("dependencies", "license_expression")
