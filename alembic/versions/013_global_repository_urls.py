"""Make repository URLs globally unique via project_repositories join table

Revision ID: 013
Revises: 012
Create Date: 2026-03-31 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Step 1: Create project_repositories table ──────────────────────────
    op.create_table(
        "project_repositories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("credentials_username", sa.String(255), nullable=True),
        sa.Column("credentials_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "repository_id", name="uq_project_repositories_project_repo"),
    )
    op.create_index("ix_project_repositories_project_id", "project_repositories", ["project_id"])
    op.create_index("ix_project_repositories_repository_id", "project_repositories", ["repository_id"])

    # ── Step 2: Populate project_repositories from existing repositories ────
    rows = conn.execute(sa.text(
        "SELECT id, project_id, name, default_branch, credentials_username, credentials_token, created_at, updated_at "
        "FROM repositories ORDER BY id"
    )).fetchall()

    for row in rows:
        conn.execute(sa.text(
            "INSERT INTO project_repositories "
            "(project_id, repository_id, name, default_branch, credentials_username, credentials_token, created_at, updated_at) "
            "VALUES (:project_id, :repository_id, :name, :default_branch, :creds_u, :creds_t, :created_at, :updated_at)"
        ), {
            "project_id": row[1],
            "repository_id": row[0],
            "name": row[2],
            "default_branch": row[3],
            "creds_u": row[4],
            "creds_t": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        })

    # ── Step 3: Reparent child tables to project_repository_id ─────────────
    # scans
    with op.batch_alter_table("scans") as batch_op:
        batch_op.add_column(sa.Column("project_repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE scans SET project_repository_id = ("
        "  SELECT pr.id FROM project_repositories pr WHERE pr.repository_id = scans.repository_id"
        ")"
    ))

    with op.batch_alter_table("scans") as batch_op:
        batch_op.alter_column("project_repository_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_scans_project_repository_id", "project_repositories",
            ["project_repository_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_index("ix_scans_repository_id")
        batch_op.drop_column("repository_id")
        batch_op.create_index("ix_scans_project_repository_id", ["project_repository_id"])

    # modules
    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(sa.Column("project_repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE modules SET project_repository_id = ("
        "  SELECT pr.id FROM project_repositories pr WHERE pr.repository_id = modules.repository_id"
        ")"
    ))

    with op.batch_alter_table("modules") as batch_op:
        batch_op.alter_column("project_repository_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_modules_project_repository_id", "project_repositories",
            ["project_repository_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_index("ix_modules_repository_id")
        batch_op.drop_column("repository_id")
        batch_op.create_index("ix_modules_project_repository_id", ["project_repository_id"])

    # repository_tags
    with op.batch_alter_table("repository_tags") as batch_op:
        batch_op.add_column(sa.Column("project_repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE repository_tags SET project_repository_id = ("
        "  SELECT pr.id FROM project_repositories pr WHERE pr.repository_id = repository_tags.repository_id"
        ")"
    ))

    with op.batch_alter_table("repository_tags") as batch_op:
        batch_op.alter_column("project_repository_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_repository_tags_project_repository_id", "project_repositories",
            ["project_repository_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_constraint("uq_repository_tags_repository_id_tag", type_="unique")
        batch_op.drop_index("ix_repository_tags_repository_id")
        batch_op.drop_column("repository_id")
        batch_op.create_index("ix_repository_tags_project_repository_id", ["project_repository_id"])
        batch_op.create_unique_constraint(
            "uq_repository_tags_project_repository_id_tag", ["project_repository_id", "tag"]
        )

    # repository_daily_activity
    with op.batch_alter_table("repository_daily_activity") as batch_op:
        batch_op.add_column(sa.Column("project_repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE repository_daily_activity SET project_repository_id = ("
        "  SELECT pr.id FROM project_repositories pr WHERE pr.repository_id = repository_daily_activity.repository_id"
        ")"
    ))

    with op.batch_alter_table("repository_daily_activity") as batch_op:
        batch_op.alter_column("project_repository_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_repository_daily_activity_project_repository_id", "project_repositories",
            ["project_repository_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_constraint("uq_repository_daily_activity_repository_date", type_="unique")
        batch_op.drop_index("ix_repository_daily_activity_repository_id")
        batch_op.drop_column("repository_id")
        batch_op.create_index("ix_repository_daily_activity_project_repository_id", ["project_repository_id"])
        batch_op.create_unique_constraint(
            "uq_repository_daily_activity_pr_id_commit_date", ["project_repository_id", "commit_date"]
        )

    # ── Step 4: Deduplicate repositories by URL ─────────────────────────────
    all_repos = conn.execute(sa.text("SELECT id, url FROM repositories ORDER BY id")).fetchall()
    url_to_ids: dict = {}
    for rid, url in all_repos:
        url_to_ids.setdefault(url, []).append(rid)

    for url, ids in url_to_ids.items():
        if len(ids) <= 1:
            continue
        keeper_id = ids[0]
        for dup_id in ids[1:]:
            conn.execute(sa.text(
                "UPDATE project_repositories SET repository_id = :keeper WHERE repository_id = :dup"
            ), {"keeper": keeper_id, "dup": dup_id})
            conn.execute(sa.text(
                "UPDATE repository_git_tags SET repository_id = :keeper WHERE repository_id = :dup"
            ), {"keeper": keeper_id, "dup": dup_id})
            conn.execute(sa.text("DELETE FROM repositories WHERE id = :id"), {"id": dup_id})

    # ── Step 5: Strip project-scoped columns from repositories ─────────────
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_constraint("uq_repositories_project_id_url", type_="unique")
        batch_op.drop_index("ix_repositories_project_id")
        batch_op.drop_column("project_id")
        batch_op.drop_column("name")
        batch_op.drop_column("default_branch")
        batch_op.drop_column("credentials_username")
        batch_op.drop_column("credentials_token")
        batch_op.create_unique_constraint("uq_repositories_url", ["url"])


def downgrade() -> None:
    conn = op.get_bind()

    # Re-add columns to repositories
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_constraint("uq_repositories_url", type_="unique")
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("default_branch", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("credentials_username", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("credentials_token", sa.Text(), nullable=True))

    # Restore from project_repositories (one-to-one: take first pr per repository)
    pr_rows = conn.execute(sa.text(
        "SELECT repository_id, project_id, name, default_branch, credentials_username, credentials_token "
        "FROM project_repositories ORDER BY id"
    )).fetchall()
    seen: set = set()
    for row in pr_rows:
        rid = row[0]
        if rid in seen:
            continue
        seen.add(rid)
        conn.execute(sa.text(
            "UPDATE repositories SET project_id=:pid, name=:name, default_branch=:db, "
            "credentials_username=:cu, credentials_token=:ct WHERE id=:rid"
        ), {"pid": row[1], "name": row[2], "db": row[3], "cu": row[4], "ct": row[5], "rid": rid})

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.alter_column("project_id", nullable=False)
        batch_op.alter_column("name", nullable=False)
        batch_op.create_index("ix_repositories_project_id", ["project_id"])
        batch_op.create_unique_constraint("uq_repositories_project_id_url", ["project_id", "url"])

    # Restore repository_daily_activity
    with op.batch_alter_table("repository_daily_activity") as batch_op:
        batch_op.add_column(sa.Column("repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE repository_daily_activity SET repository_id = ("
        "  SELECT pr.repository_id FROM project_repositories pr "
        "  WHERE pr.id = repository_daily_activity.project_repository_id"
        ")"
    ))

    with op.batch_alter_table("repository_daily_activity") as batch_op:
        batch_op.alter_column("repository_id", nullable=False)
        batch_op.drop_constraint("uq_repository_daily_activity_pr_id_commit_date", type_="unique")
        batch_op.drop_index("ix_repository_daily_activity_project_repository_id")
        batch_op.drop_column("project_repository_id")
        batch_op.create_index("ix_repository_daily_activity_repository_id", ["repository_id"])
        batch_op.create_unique_constraint(
            "uq_repository_daily_activity_repository_date", ["repository_id", "commit_date"]
        )

    # Restore repository_tags
    with op.batch_alter_table("repository_tags") as batch_op:
        batch_op.add_column(sa.Column("repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE repository_tags SET repository_id = ("
        "  SELECT pr.repository_id FROM project_repositories pr "
        "  WHERE pr.id = repository_tags.project_repository_id"
        ")"
    ))

    with op.batch_alter_table("repository_tags") as batch_op:
        batch_op.alter_column("repository_id", nullable=False)
        batch_op.drop_constraint("uq_repository_tags_project_repository_id_tag", type_="unique")
        batch_op.drop_index("ix_repository_tags_project_repository_id")
        batch_op.drop_column("project_repository_id")
        batch_op.create_index("ix_repository_tags_repository_id", ["repository_id"])
        batch_op.create_unique_constraint(
            "uq_repository_tags_repository_id_tag", ["repository_id", "tag"]
        )

    # Restore modules
    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(sa.Column("repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE modules SET repository_id = ("
        "  SELECT pr.repository_id FROM project_repositories pr "
        "  WHERE pr.id = modules.project_repository_id"
        ")"
    ))

    with op.batch_alter_table("modules") as batch_op:
        batch_op.alter_column("repository_id", nullable=False)
        batch_op.drop_index("ix_modules_project_repository_id")
        batch_op.drop_column("project_repository_id")
        batch_op.create_index("ix_modules_repository_id", ["repository_id"])

    # Restore scans
    with op.batch_alter_table("scans") as batch_op:
        batch_op.add_column(sa.Column("repository_id", sa.Integer(), nullable=True))

    conn.execute(sa.text(
        "UPDATE scans SET repository_id = ("
        "  SELECT pr.repository_id FROM project_repositories pr "
        "  WHERE pr.id = scans.project_repository_id"
        ")"
    ))

    with op.batch_alter_table("scans") as batch_op:
        batch_op.alter_column("repository_id", nullable=False)
        batch_op.drop_index("ix_scans_project_repository_id")
        batch_op.drop_column("project_repository_id")
        batch_op.create_index("ix_scans_repository_id", ["repository_id"])

    op.drop_index("ix_project_repositories_repository_id", "project_repositories")
    op.drop_index("ix_project_repositories_project_id", "project_repositories")
    op.drop_table("project_repositories")
