"""Add 'github' to providertype enum

Revision ID: 004
Revises: 003
Create Date: 2025-03-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'providertype' AND e.enumlabel = 'github'
                ) THEN
                    ALTER TYPE providertype ADD VALUE 'github';
                END IF;
            END $$
        """)
    # SQLite and others: enum stored as string; no schema change needed


def downgrade() -> None:
    # PostgreSQL: removing an enum value requires recreating type; skip
    # SQLite: no change
    pass
