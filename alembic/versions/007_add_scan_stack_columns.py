"""Add stack columns to scans table

Revision ID: 007
Revises: 006
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("frameworks_json", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("package_managers_json", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("ci_provider", sa.String(64), nullable=True))
    op.add_column("scans", sa.Column("infra_tools_json", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("linters_json", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("has_docker", sa.Boolean(), nullable=True))
    op.add_column("scans", sa.Column("has_kubernetes", sa.Boolean(), nullable=True))
    op.add_column("scans", sa.Column("has_terraform", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "has_terraform")
    op.drop_column("scans", "has_kubernetes")
    op.drop_column("scans", "has_docker")
    op.drop_column("scans", "linters_json")
    op.drop_column("scans", "infra_tools_json")
    op.drop_column("scans", "ci_provider")
    op.drop_column("scans", "package_managers_json")
    op.drop_column("scans", "frameworks_json")
