"""Drop unique constraint on (project_id, repository_id) in project_repositories

Revision ID: 014
Revises: 013
Create Date: 2026-03-31 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.drop_constraint("uq_project_repositories_project_repo", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.create_unique_constraint(
            "uq_project_repositories_project_repo", ["project_id", "repository_id"]
        )
