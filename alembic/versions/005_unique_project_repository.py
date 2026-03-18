"""Unique (project_id, url) on repositories and delete duplicates

Revision ID: 005
Revises: 004
Create Date: 2025-03-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Find all repositories and group by (project_id, url)
    rows = conn.execute(
        sa.text("SELECT id, project_id, url FROM repositories ORDER BY project_id, url, id")
    ).fetchall()

    # Build groups: (project_id, url) -> list of ids (sorted, so min = first)
    groups: dict[tuple[int, str], list[int]] = {}
    for row in rows:
        key = (row[1], row[2])
        groups.setdefault(key, []).append(row[0])

    duplicate_ids: list[int] = []
    for ids in groups.values():
        if len(ids) > 1:
            # Keep the first (smallest id), mark the rest as duplicates
            duplicate_ids.extend(ids[1:])

    for dup_id in duplicate_ids:
        # Find keeper for this duplicate (same project_id, url, min id)
        dup_row = conn.execute(
            sa.text("SELECT project_id, url FROM repositories WHERE id = :id"),
            {"id": dup_id},
        ).fetchone()
        if not dup_row:
            continue
        project_id, url = dup_row[0], dup_row[1]
        keeper_row = conn.execute(
            sa.text(
                "SELECT id FROM repositories WHERE project_id = :pid AND url = :url ORDER BY id LIMIT 1"
            ),
            {"pid": project_id, "url": url},
        ).fetchone()
        keeper_id = keeper_row[0] if keeper_row else None
        if keeper_id is None or keeper_id == dup_id:
            continue

        # Delete tags for the duplicate repo (avoids (repository_id, tag) uniqueness issues)
        conn.execute(sa.text("DELETE FROM repository_tags WHERE repository_id = :id"), {"id": dup_id})
        # Reassign scans and modules to the keeper
        conn.execute(
            sa.text("UPDATE scans SET repository_id = :keeper WHERE repository_id = :dup"),
            {"keeper": keeper_id, "dup": dup_id},
        )
        conn.execute(
            sa.text("UPDATE modules SET repository_id = :keeper WHERE repository_id = :dup"),
            {"keeper": keeper_id, "dup": dup_id},
        )
        # Delete the duplicate repository
        conn.execute(sa.text("DELETE FROM repositories WHERE id = :id"), {"id": dup_id})

    # SQLite does not support ALTER ADD/DROP constraint; use batch (copy-and-move)
    with op.batch_alter_table("repositories", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_repositories_project_id_url",
            ["project_id", "url"],
        )


def downgrade() -> None:
    with op.batch_alter_table("repositories", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_repositories_project_id_url",
            type_="unique",
        )
