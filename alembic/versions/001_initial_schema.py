"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("provider_type", sa.Enum("bitbucket", "gitlab", name="providertype"), nullable=False),
        sa.Column("default_branch", sa.String(255), server_default="main"),
        sa.Column("clone_path", sa.Text, nullable=True),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column("credentials_username", sa.String(255), nullable=True),
        sa.Column("credentials_token", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])

    op.create_table(
        "developers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_developers_project_id", "developers", ["project_id"])

    op.create_table(
        "developer_identities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("developer_id", sa.Integer, sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_name", sa.String(255), nullable=False),
        sa.Column("raw_email", sa.String(255), nullable=True),
        sa.Column("confidence_score", sa.Float, server_default="1.0"),
        sa.Column("is_ambiguous", sa.Boolean, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_developer_identities_developer_id", "developer_identities", ["developer_id"])

    op.create_table(
        "identity_overrides",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_name", sa.String(255), nullable=True),
        sa.Column("raw_email", sa.String(255), nullable=True),
        sa.Column("canonical_username", sa.String(128), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_identity_overrides_project_id", "identity_overrides", ["project_id"])

    op.create_table(
        "languages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repository_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", name="scanstatus"), nullable=False, server_default="pending"),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("total_files", sa.Integer, nullable=True),
        sa.Column("total_loc", sa.Integer, nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("file_count_source", sa.Integer, nullable=True),
        sa.Column("file_count_test", sa.Integer, nullable=True),
        sa.Column("file_count_config", sa.Integer, nullable=True),
        sa.Column("dir_count", sa.Integer, nullable=True),
        sa.Column("project_type", sa.Enum("backend_service", "frontend_application", "library", "cli_tool", "infra_config", "monolith", "monorepo", "unknown", name="projecttype"), nullable=True),
        sa.Column("primary_language", sa.String(64), nullable=True),
        sa.Column("avg_file_loc", sa.Float, nullable=True),
        sa.Column("large_files_count", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_scans_repository_id", "scans", ["repository_id"])

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repository_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_modules_repository_id", "modules", ["repository_id"])

    op.create_table(
        "scan_languages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_id", sa.Integer, sa.ForeignKey("languages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_count", sa.Integer, server_default="0"),
        sa.Column("loc", sa.Integer, server_default="0"),
        sa.Column("percentage", sa.Float, server_default="0.0"),
    )
    op.create_index("ix_scan_languages_scan_id", "scan_languages", ["scan_id"])

    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(128), nullable=True),
        sa.Column("dep_type", sa.Enum("prod", "dev", "test", "unknown", name="dependencytype"), server_default="unknown"),
        sa.Column("manifest_file", sa.String(255), nullable=True),
        sa.Column("ecosystem", sa.String(64), nullable=True),
    )
    op.create_index("ix_dependencies_scan_id", "dependencies", ["scan_id"])

    op.create_table(
        "developer_contributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("developer_id", sa.Integer, sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer, server_default="0"),
        sa.Column("insertions", sa.Integer, server_default="0"),
        sa.Column("deletions", sa.Integer, server_default="0"),
        sa.Column("files_changed", sa.Integer, server_default="0"),
        sa.Column("active_days", sa.Integer, server_default="0"),
        sa.Column("first_commit_at", sa.DateTime, nullable=True),
        sa.Column("last_commit_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_developer_contributions_scan_id", "developer_contributions", ["scan_id"])
    op.create_index("ix_developer_contributions_developer_id", "developer_contributions", ["developer_id"])

    op.create_table(
        "developer_language_contributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("developer_id", sa.Integer, sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_id", sa.Integer, sa.ForeignKey("languages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer, server_default="0"),
        sa.Column("files_changed", sa.Integer, server_default="0"),
        sa.Column("loc_added", sa.Integer, server_default="0"),
        sa.Column("loc_deleted", sa.Integer, server_default="0"),
        sa.Column("percentage", sa.Float, server_default="0.0"),
    )
    op.create_index("ix_developer_language_contributions_scan_id", "developer_language_contributions", ["scan_id"])
    op.create_index("ix_developer_language_contributions_developer_id", "developer_language_contributions", ["developer_id"])

    op.create_table(
        "developer_module_contributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("developer_id", sa.Integer, sa.ForeignKey("developers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commit_count", sa.Integer, server_default="0"),
        sa.Column("files_changed", sa.Integer, server_default="0"),
        sa.Column("loc_added", sa.Integer, server_default="0"),
        sa.Column("percentage", sa.Float, server_default="0.0"),
    )
    op.create_index("ix_developer_module_contributions_scan_id", "developer_module_contributions", ["scan_id"])
    op.create_index("ix_developer_module_contributions_developer_id", "developer_module_contributions", ["developer_id"])

    op.create_table(
        "scan_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.Enum("code_quality", "test_quality", "doc_quality", "delivery_quality", "maintainability", "overall", name="scoredomain"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("details", sa.Text, nullable=True),
    )
    op.create_index("ix_scan_scores_scan_id", "scan_scores", ["scan_id"])

    op.create_table(
        "scan_risks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_type", sa.Enum(
            "high_complexity_module", "no_tests", "weak_documentation", "no_ci_pipeline",
            "no_lockfile", "oversized_file", "oversized_function", "oversized_module",
            "knowledge_concentration", "low_bus_factor", "orphan_module",
            "mono_owner_language", "mono_owner_module", name="risktype"
        ), nullable=False),
        sa.Column("severity", sa.Enum("low", "medium", "high", "critical", name="riskseverity"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("entity_type", sa.Enum("project", "module", "developer", "language", "file", name="entitytype"), nullable=True),
        sa.Column("entity_ref", sa.String(255), nullable=True),
    )
    op.create_index("ix_scan_risks_scan_id", "scan_risks", ["scan_id"])


def downgrade() -> None:
    op.drop_table("scan_risks")
    op.drop_table("scan_scores")
    op.drop_table("developer_module_contributions")
    op.drop_table("developer_language_contributions")
    op.drop_table("developer_contributions")
    op.drop_table("dependencies")
    op.drop_table("scan_languages")
    op.drop_table("modules")
    op.drop_table("scans")
    op.drop_table("languages")
    op.drop_table("identity_overrides")
    op.drop_table("developer_identities")
    op.drop_table("developers")
    op.drop_table("repositories")
    op.drop_table("projects")
