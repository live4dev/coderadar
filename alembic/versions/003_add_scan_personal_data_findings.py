"""Add scan_personal_data_findings table for PDn search results

Revision ID: 003
Revises: 002
Create Date: 2025-03-14 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scan_personal_data_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pdn_type", sa.String(128), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("matched_identifier", sa.String(255), nullable=False),
    )
    op.create_index("ix_scan_personal_data_findings_scan_id", "scan_personal_data_findings", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_scan_personal_data_findings_scan_id", table_name="scan_personal_data_findings")
    op.drop_table("scan_personal_data_findings")
